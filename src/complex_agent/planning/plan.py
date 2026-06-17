from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from complex_agent.core.modes import TaskStatus
from complex_agent.planning.plan_step import PlanStep
from complex_agent.utils.ids import new_id


@dataclass(slots=True)
class Plan:
    id: str
    task_id: str
    goal: str
    steps: list[PlanStep]
    risks: list[str] = field(default_factory=list)
    approval_points: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: TaskStatus = TaskStatus.PLANNED

    @classmethod
    def create(cls, *, task_id: str, goal: str, steps: list[PlanStep]) -> "Plan":
        return cls(id=new_id("plan"), task_id=task_id, goal=goal, steps=steps)

