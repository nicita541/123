from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from complex_agent.core.observation import Observation
from complex_agent.core.result import Result
from complex_agent.core.step import Step
from complex_agent.core.task import Task

if TYPE_CHECKING:
    from complex_agent.planning.plan import Plan


@dataclass(slots=True)
class AgentState:
    task: Task
    current_plan: "Plan | None" = None
    completed_steps: list[Step] = field(default_factory=list)
    failed_steps: list[Step] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    memory_snapshot: dict[str, Any] = field(default_factory=dict)
    changed_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    iteration_count: int = 0
    replan_count: int = 0
    final_result: Result | None = None

    def add_observation(self, observation: Observation) -> None:
        self.observations.append(observation)
        if not observation.success and observation.error:
            self.errors.append(observation.error)

    def record_changed_files(self, files: list[str]) -> None:
        for file_name in files:
            if file_name not in self.changed_files:
                self.changed_files.append(file_name)

