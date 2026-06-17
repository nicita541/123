from __future__ import annotations

from complex_agent.core.errors import PlanValidationError
from complex_agent.planning.plan import Plan


class PlanValidator:
    def validate(self, plan: Plan) -> None:
        if not plan.goal.strip():
            raise PlanValidationError("Plan goal is empty.")
        if not plan.steps:
            raise PlanValidationError("Plan has no steps.")
        seen: set[str] = set()
        for step in plan.steps:
            if step.id in seen:
                raise PlanValidationError(f"Duplicate step id: {step.id}")
            seen.add(step.id)
            if not step.required_tool:
                raise PlanValidationError(f"Step {step.id} has no required tool.")

