from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from complex_agent.core.modes import RiskLevel
from complex_agent.core.task import Task
from complex_agent.llm.ollama_provider import OllamaError, OllamaProvider
from complex_agent.planning.plan import Plan
from complex_agent.planning.plan_step import PlanStep
from complex_agent.safety.safety_policy import SafetyPolicy


ALLOWED_PLAN_TOOLS = {"read_file", "apply_patch", "shell", "final_report"}


@dataclass(slots=True)
class OllamaPlanMetadata:
    goal: str
    summary: str
    expected_files: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)


class OllamaPlanner:
    def __init__(self, provider: OllamaProvider, safety: SafetyPolicy) -> None:
        self.provider = provider
        self.safety = safety

    def create_plan(self, task: Task) -> tuple[Plan, OllamaPlanMetadata]:
        self.provider.select_available_model()
        context = _project_context(self.safety.project_root, self.safety)
        schema_hint = _schema_hint()
        last_error: Exception | None = None
        for strict in (False, True):
            prompt = _plan_prompt(task.normalized_goal, context, strict=strict)
            try:
                raw = self.provider.complete_structured(prompt, schema_hint)
                return self._build_plan(task, raw)
            except Exception as exc:  # noqa: BLE001 - retry once with stricter prompt
                last_error = exc
        raise OllamaError(f"Ollama returned invalid plan JSON: {last_error}")

    def _build_plan(self, task: Task, raw: dict[str, Any] | str) -> tuple[Plan, OllamaPlanMetadata]:
        if not isinstance(raw, dict):
            raise OllamaError("Plan response must be a JSON object.")
        goal = _required_text(raw, "goal")
        summary = _required_text(raw, "summary")
        raw_steps = raw.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise OllamaError("Plan response must contain a non-empty steps list.")

        expected_files = _safe_path_list(raw.get("expected_files", []), self.safety)
        verification = _safe_verification_list(raw.get("verification", []), self.safety)

        steps: list[PlanStep] = []
        for item in raw_steps[:8]:
            if not isinstance(item, dict):
                continue
            tool = str(item.get("tool", "final_report"))
            if tool not in ALLOWED_PLAN_TOOLS:
                tool = "final_report"
            risk = _risk(str(item.get("risk", "low")))
            requires_approval = bool(item.get("requires_approval", tool == "apply_patch"))
            steps.append(
                PlanStep.create(
                    type=str(item.get("title", tool)).lower().replace(" ", "_")[:48] or tool,
                    description=str(item.get("description") or item.get("title") or "Ollama plan step."),
                    required_tool=tool,
                    input={},
                    risk_level=risk,
                    approval_required=requires_approval or tool == "apply_patch",
                )
            )
        if not any(step.required_tool == "apply_patch" for step in steps):
            steps.append(
                PlanStep.create(
                    type="propose_patch",
                    description="Prepare a proposed unified diff for approval.",
                    required_tool="apply_patch",
                    risk_level=RiskLevel.HIGH,
                    approval_required=True,
                )
            )
        for command in verification:
            steps.append(
                PlanStep.create(
                    type="verification",
                    description=f"Run safe verification: {command}",
                    required_tool="shell",
                    input={"command": command},
                    risk_level=RiskLevel.MEDIUM,
                )
            )
        steps.append(
            PlanStep.create(
                type="report",
                description="Prepare final report after approved changes and checks.",
                required_tool="final_report",
                input={"message": task.normalized_goal},
            )
        )

        plan = Plan.create(task_id=task.id, goal=goal or task.normalized_goal, steps=steps)
        plan.approval_points.append("Ollama-generated patches must be validated and approved before write.")
        metadata = OllamaPlanMetadata(
            goal=goal,
            summary=summary,
            expected_files=expected_files,
            verification=verification,
        )
        if expected_files:
            plan.risks.append("Expected files: " + ", ".join(expected_files))
        return plan, metadata


def _schema_hint() -> dict[str, Any]:
    return {
        "goal": "string",
        "summary": "string",
        "steps": [
            {
                "title": "string",
                "description": "string",
                "tool": "read_file|apply_patch|shell|final_report",
                "risk": "low|medium|high",
                "requires_approval": True,
            }
        ],
        "expected_files": ["relative/path.py"],
        "verification": ["python -m py_compile relative/path.py"],
    }


def _plan_prompt(task_text: str, context: str, *, strict: bool) -> str:
    retry = (
        "Your previous answer was invalid. Return JSON only and exactly match the requested schema. "
        if strict
        else ""
    )
    return (
        f"{retry}"
        "You are the planner for a local safe coding agent. Return only JSON, no markdown. "
        "Create a concise implementation plan for the user task. "
        "Use only these tools: read_file, apply_patch, shell, final_report. "
        "Every file path must be relative to the selected project root. "
        "Never use absolute paths, '..', .env, .agent, .venv, __pycache__, secret, token, credentials, or private-key paths. "
        "Verification commands must be safe, non-interactive, and allowlisted, for example python -m py_compile file.py. "
        "Never propose rm -rf, del /s, git reset, git clean, git push, network install, or interactive commands. "
        f"Selected project context:\n{context}\n\n"
        f"Task:\n{task_text}"
    )


def _project_context(project_root: Path, safety: SafetyPolicy) -> str:
    lines: list[str] = [f"project_root={project_root}"]
    files: list[str] = []
    for path in project_root.rglob("*"):
        if len(files) >= 80:
            break
        if not path.is_file():
            continue
        allowed, _ = safety.file_guard.validate_read(path)
        if not allowed:
            continue
        try:
            files.append(path.relative_to(project_root).as_posix())
        except ValueError:
            continue
    if files:
        lines.append("safe_files:")
        lines.extend(f"- {item}" for item in sorted(files))
    else:
        lines.append("safe_files: none")
    return "\n".join(lines)


def _required_text(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OllamaError(f"Plan response missing text field: {key}")
    return value.strip()


def _safe_path_list(value: object, safety: SafetyPolicy) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value[:20]:
        if not isinstance(item, str):
            continue
        path = item.strip().replace("\\", "/")
        if not path:
            continue
        allowed, reason = safety.file_guard.validate_write(safety.project_root / path)
        if not allowed:
            raise OllamaError(f"Unsafe expected file path rejected: {path}: {reason}")
        result.append(path)
    return result


def _safe_verification_list(value: object, safety: SafetyPolicy) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value[:5]:
        if not isinstance(item, str):
            continue
        command = item.strip()
        if not command:
            continue
        decision = safety.check_command(command)
        if not decision.allowed or decision.requires_approval:
            raise OllamaError(f"Unsafe verification command rejected: {command}: {decision.reason}")
        result.append(command)
    return result


def _risk(value: str) -> RiskLevel:
    normalized = value.lower()
    if normalized == "high":
        return RiskLevel.HIGH
    if normalized == "medium":
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
