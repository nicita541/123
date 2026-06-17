from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from complex_agent.core.modes import RiskLevel, StepStatus
from complex_agent.utils.ids import new_id


@dataclass(slots=True)
class PlanStep:
    id: str
    type: str
    description: str
    required_tool: str
    input: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    approval_required: bool = False
    status: StepStatus = StepStatus.PENDING

    @classmethod
    def create(
        cls,
        *,
        type: str,
        description: str,
        required_tool: str,
        input: dict[str, Any] | None = None,
        risk_level: RiskLevel = RiskLevel.LOW,
        approval_required: bool = False,
    ) -> "PlanStep":
        return cls(
            id=new_id("step"),
            type=type,
            description=description,
            required_tool=required_tool,
            input=input or {},
            risk_level=risk_level,
            approval_required=approval_required,
        )

