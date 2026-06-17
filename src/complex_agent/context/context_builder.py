from __future__ import annotations

from dataclasses import dataclass, field

from complex_agent.context.context_item import ContextItem
from complex_agent.core.task import Task


@dataclass(slots=True)
class ContextBundle:
    task_id: str
    items: list[ContextItem] = field(default_factory=list)
    token_budget: int = 4000

    def add(self, item: ContextItem) -> None:
        self.items.append(item)


class ContextBuilder:
    def build_initial_context(self, task: Task) -> ContextBundle:
        bundle = ContextBundle(task_id=task.id)
        bundle.add(
            ContextItem(
                source="user_request",
                content=task.user_request,
                summary=task.normalized_goal,
                metadata={"mode": task.mode.value, "project_path": str(task.project_path)},
            )
        )
        return bundle

