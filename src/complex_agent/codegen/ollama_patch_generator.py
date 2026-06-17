from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from complex_agent.llm.ollama_provider import OllamaError, OllamaProvider
from complex_agent.planning.plan import Plan
from complex_agent.safety.safety_policy import SafetyPolicy


@dataclass(frozen=True, slots=True)
class OllamaPatch:
    patch: str
    changed_files: list[str]
    summary: str


class OllamaPatchGenerator:
    def __init__(self, provider: OllamaProvider, safety: SafetyPolicy) -> None:
        self.provider = provider
        self.safety = safety

    def propose(self, *, task_text: str, plan: Plan | None, project_root: Path) -> OllamaPatch:
        self.provider.select_available_model()
        context = _project_context(project_root, self.safety)
        plan_text = _plan_text(plan)
        last_error: Exception | None = None
        for strict in (False, True):
            prompt = _patch_prompt(task_text, plan_text, context, strict=strict)
            try:
                text = self.provider.complete(prompt).strip()
                patch = self.extract_diff(text)
                self.validate_patch(patch)
                return OllamaPatch(
                    patch=patch,
                    changed_files=extract_patch_paths(patch),
                    summary=f"Ollama ({self.provider.model}) proposed a validated unified diff.",
                )
            except Exception as exc:  # noqa: BLE001 - retry once with stricter prompt
                last_error = exc
        raise OllamaError(f"Ollama did not produce a valid unified diff: {last_error}")

    def extract_diff(self, text: str) -> str:
        if not text:
            raise OllamaError("Ollama returned an empty patch response.")
        if "```" in text:
            raise OllamaError("Markdown fenced patches are not accepted.")
        stripped = text.strip()
        if not (stripped.startswith("--- ") or stripped.startswith("diff --git ")):
            raise OllamaError("Patch response must start with a unified diff header.")
        return stripped + "\n"

    def validate_patch(self, patch: str) -> None:
        if self.safety.redact(patch) != patch:
            raise ValueError("Patch contains secret-like content and was rejected.")
        if not patch.strip():
            raise ValueError("Patch is empty.")
        paths = extract_patch_paths(patch)
        if not paths:
            raise ValueError("Patch does not contain target files.")
        for path in paths:
            if path.startswith("/") or path.startswith("\\"):
                raise ValueError(f"Absolute patch path rejected: {path}")
            if ".." in Path(path).parts or "../" in path.replace("\\", "/"):
                raise ValueError(f"Path traversal rejected: {path}")
            allowed, reason = self.safety.file_guard.validate_write(self.safety.project_root / path)
            if not allowed:
                raise ValueError(reason)


def extract_patch_paths(patch: str) -> list[str]:
    paths: list[str] = []
    for line in patch.splitlines():
        if not line.startswith(("--- ", "+++ ")):
            continue
        raw = line[4:].strip().split("\t", 1)[0].split(" ", 1)[0]
        if raw == "/dev/null":
            continue
        path = raw[2:] if raw.startswith(("a/", "b/")) else raw
        if path not in paths:
            paths.append(path)
    return paths


def _patch_prompt(task_text: str, plan_text: str, context: str, *, strict: bool) -> str:
    retry = (
        "Your previous answer was invalid. Return ONLY a valid unified diff. "
        if strict
        else ""
    )
    return (
        f"{retry}"
        "You are the patch generator for a local safe coding agent. "
        "Return ONLY a unified diff. Do not wrap in markdown. Do not add explanations. "
        "Use relative paths only. Use /dev/null for new files and b/<relative-path> for targets. "
        "Do not touch .env, .agent, .venv, __pycache__, .git, secret, token, credential, or private-key paths. "
        "Do not use absolute paths or path traversal. "
        "Prefer small, self-contained changes. "
        "If creating a Python file, include syntactically valid Python and avoid interactive verification commands. "
        f"Selected project context:\n{context}\n\n"
        f"Plan:\n{plan_text}\n\n"
        f"Task:\n{task_text}"
    )


def _project_context(project_root: Path, safety: SafetyPolicy) -> str:
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
    return "\n".join(f"- {path}" for path in sorted(files)) if files else "No safe files found."


def _plan_text(plan: Plan | None) -> str:
    if plan is None:
        return "No prior plan."
    lines = [f"Goal: {plan.goal}"]
    for index, step in enumerate(plan.steps, start=1):
        lines.append(f"{index}. {step.description} [tool={step.required_tool}, risk={step.risk_level.value}]")
    if plan.risks:
        lines.append("Risks: " + "; ".join(plan.risks))
    return "\n".join(lines)
