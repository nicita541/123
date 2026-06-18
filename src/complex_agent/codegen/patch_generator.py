from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from complex_agent.codegen.ollama_patch_generator import OllamaPatchGenerator
from complex_agent.core.task import Task
from complex_agent.llm.ollama_provider import OllamaError, OllamaProvider, OllamaSettings, load_ollama_settings
from complex_agent.planning.ollama_planner import OllamaPlanner
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
        allow_demo_fallback: bool | None = None,
    ) -> None:
        self.safety = safety
        self.settings = settings or load_ollama_settings()
        self.ollama_provider = ollama_provider or OllamaProvider.from_settings(self.settings)
        self.allow_demo_fallback = (
            _env_truthy("AGENT_ENABLE_DEMO_FALLBACK")
            if allow_demo_fallback is None
            else allow_demo_fallback
        )
        self._calculator = PythonCalculatorSkill()
        self._ollama_planner = OllamaPlanner(self.ollama_provider, safety)
        self._ollama_patch_generator = OllamaPatchGenerator(self.ollama_provider, safety)

    def supports(self, task_text: str) -> bool:
        return self.allow_demo_fallback and self._calculator.supports(task_text)

    def llm_status(self, *, include_generation_check: bool = True) -> dict[str, object]:
        reachable = False
        generation_check = False
        error = ""
        models: list[str] = []
        try:
            models = self.ollama_provider.select_available_model()
            reachable = True
            if include_generation_check:
                generation_check = self.ollama_provider.generation_check()
        except Exception as exc:  # noqa: BLE001 - status must not break read-only calls
            error = str(exc)
        return {
            "llm_provider": self.settings.provider,
            "fallback_provider": self.settings.fallback_provider,
            "ollama_base_url": self.settings.base_url,
            "ollama_model": self.ollama_provider.model,
            "ollama_reachable": reachable,
            "ollama_generation_check": generation_check,
            "ollama_models": models,
            "ollama_error": error,
            "demo_fallback_enabled": self.allow_demo_fallback,
        }

    def create_plan(self, task: Task) -> Plan:
        if self.supports(task.normalized_goal):
            return self._calculator.create_plan(task)
        try:
            plan, _metadata = self._ollama_planner.create_plan(task)
            return plan
        except OllamaError as exc:
            return _ollama_unavailable_plan(task, exc)

    def propose(self, task: Task, project_root: Path, *, plan: Plan | None = None) -> ProposedPatch:
        if self.supports(task.normalized_goal):
            calculator_proposal = self._calculator.propose(task, project_root)
            self.validate_patch(calculator_proposal.patch)
            return ProposedPatch(
                skill_name=self._calculator.name,
                patch=calculator_proposal.patch,
                changed_files=calculator_proposal.changed_files,
                summary=calculator_proposal.summary,
            )
        ollama_proposal = self._ollama_patch_generator.propose(
            task_text=task.normalized_goal,
            plan=plan,
            project_root=project_root,
        )
        return ProposedPatch(
            skill_name="ollama",
            patch=ollama_proposal.patch,
            changed_files=ollama_proposal.changed_files,
            summary=ollama_proposal.summary,
        )

    def validate_patch(self, patch: str) -> None:
        self._ollama_patch_generator.validate_patch(patch)


def _ollama_unavailable_plan(task: Task, exc: Exception) -> Plan:
    plan = Plan.create(
        task_id=task.id,
        goal=task.normalized_goal,
        steps=[
            PlanStep.create(
                type="llm_unavailable",
                description=(
                    "Ollama недоступна. Задача не может быть выполнена без локальной модели."
                ),
                required_tool="final_report",
                input={"message": task.normalized_goal, "error": str(exc)},
            )
        ],
    )
    plan.risks.append(f"Ollama unavailable: {exc}")
    return plan


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
