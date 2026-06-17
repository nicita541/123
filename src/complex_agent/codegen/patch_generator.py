from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from complex_agent.core.task import Task
from complex_agent.llm.ollama_provider import OllamaError, OllamaProvider, OllamaSettings, load_ollama_settings
from complex_agent.planning.plan import Plan
from complex_agent.planning.plan_step import PlanStep
from complex_agent.safety.safety_policy import SafetyPolicy
from complex_agent.skills.python_calculator_skill import PythonCalculatorSkill


@dataclass(frozen=True, slots=True)
class ProposedPatch:
    skill_name: str
    patch: str
    changed_files: list[str]
    summary: str


class PatchGenerator:
    def __init__(
        self,
        safety: SafetyPolicy,
        *,
        settings: OllamaSettings | None = None,
        ollama_provider: OllamaProvider | None = None,
    ) -> None:
        self.safety = safety
        self.settings = settings or load_ollama_settings()
        self.ollama_provider = ollama_provider or OllamaProvider.from_settings(self.settings)
        self._calculator = PythonCalculatorSkill()

    def supports(self, task_text: str) -> bool:
        return self._calculator.supports(task_text)

    def llm_status(self) -> dict[str, object]:
        reachable = False
        error = ""
        try:
            reachable = self.ollama_provider.is_reachable()
        except Exception as exc:  # noqa: BLE001 - status must not break read-only calls
            error = str(exc)
        return {
            "llm_provider": self.settings.provider,
            "fallback_provider": self.settings.fallback_provider,
            "ollama_base_url": self.settings.base_url,
            "ollama_model": self.settings.model,
            "ollama_reachable": reachable,
            "ollama_error": error,
        }

    def create_plan(self, task: Task) -> Plan:
        if self.supports(task.normalized_goal):
            return self._calculator.create_plan(task)
        try:
            return self._create_ollama_plan(task)
        except OllamaError as exc:
            plan = Plan.create(
                task_id=task.id,
                goal=task.normalized_goal,
                steps=[
                    PlanStep.create(
                        type="llm_unavailable",
                        description=f"Ollama недоступен: {exc}. Доступен deterministic fallback.",
                        required_tool="final_report",
                        input={"message": task.normalized_goal},
                    )
                ],
            )
            plan.risks.append("Ollama unavailable; no patch will be proposed for unknown task.")
            return plan

    def _create_ollama_plan(self, task: Task) -> Plan:
        response = self.ollama_provider.complete_structured(
            _plan_prompt(task.normalized_goal),
            {
                "steps": [
                    {
                        "type": "analysis",
                        "description": "Short implementation step",
                        "tool": "read_file|search_files|apply_patch|shell|final_report",
                        "risk": "low|medium|high",
                    }
                ],
                "risks": ["optional risks"],
            },
        )
        if not isinstance(response, dict) or not isinstance(response.get("steps"), list):
            raise OllamaError("Ollama plan response must be a JSON object with a steps list.")

        steps: list[PlanStep] = []
        allowed_tools = {"read_file", "search_files", "apply_patch", "shell", "final_report"}
        for raw in response["steps"][:8]:
            if not isinstance(raw, dict):
                continue
            tool = str(raw.get("tool", "final_report"))
            steps.append(
                PlanStep.create(
                    type=str(raw.get("type", "analysis")),
                    description=str(raw.get("description", "Шаг плана от локальной модели.")),
                    required_tool=tool if tool in allowed_tools else "final_report",
                    input={},
                    approval_required=tool == "apply_patch",
                )
            )
        if not steps:
            raise OllamaError("Ollama plan did not contain usable steps.")

        plan = Plan.create(task_id=task.id, goal=task.normalized_goal, steps=steps)
        risks = response.get("risks", [])
        if isinstance(risks, list):
            plan.risks.extend(str(item) for item in risks[:5])
        plan.approval_points.append(
            "Любой patch от Ollama требует проверки и подтверждения."
        )
        return plan

    def propose(self, task: Task, project_root: Path) -> ProposedPatch:
        if not self.supports(task.normalized_goal):
            return self._propose_with_ollama(task)
        proposal = self._calculator.propose(task, project_root)
        self.validate_patch(proposal.patch)
        return ProposedPatch(
            skill_name=self._calculator.name,
            patch=proposal.patch,
            changed_files=proposal.changed_files,
            summary=proposal.summary,
        )

    def _propose_with_ollama(self, task: Task) -> ProposedPatch:
        text = self.ollama_provider.complete(_patch_prompt(task.normalized_goal)).strip()
        patch = _extract_diff(text)
        self.validate_patch(patch)
        return ProposedPatch(
            skill_name="ollama",
            patch=patch,
            changed_files=_extract_patch_paths(patch),
            summary="Ollama предложил unified diff. Patch требует подтверждения.",
        )

    def validate_patch(self, patch: str) -> None:
        if not patch.strip():
            raise ValueError("Patch is empty.")
        paths = _extract_patch_paths(patch)
        if not paths:
            raise ValueError("Patch does not contain target files.")
        for path in paths:
            allowed, reason = self.safety.file_guard.validate_write(self.safety.project_root / path)
            if not allowed:
                raise ValueError(reason)


def _extract_patch_paths(patch: str) -> list[str]:
    paths: list[str] = []
    for line in patch.splitlines():
        if not line.startswith(("--- ", "+++ ")):
            continue
        raw = line[4:].strip()
        if raw == "/dev/null":
            continue
        path = raw[2:] if raw.startswith(("a/", "b/")) else raw
        if path not in paths:
            paths.append(path)
    return paths


def _plan_prompt(task_text: str) -> str:
    return (
        "Ты локальный coding-agent planner. Верни только JSON без markdown. "
        "Не предлагай прямую запись файлов и не запускай команды. "
        f"Задача: {task_text}"
    )


def _patch_prompt(task_text: str) -> str:
    return (
        "Ты локальный coding-agent. Предложи только unified diff для задачи. "
        "Не используй .env, .agent, .venv, __pycache__, secret/token/private key paths. "
        "Не добавляй объяснения вне diff. "
        f"Задача: {task_text}"
    )


def _extract_diff(text: str) -> str:
    if "```" in text:
        chunks = text.split("```")
        for chunk in chunks:
            candidate = chunk.strip()
            if candidate.startswith("diff") or candidate.startswith("--- "):
                return candidate + "\n"
    start = text.find("--- ")
    if start == -1:
        start = text.find("diff --git ")
    if start == -1:
        raise OllamaError("Ollama did not return a unified diff.")
    return text[start:].strip() + "\n"
