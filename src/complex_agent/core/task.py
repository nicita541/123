from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from complex_agent.core.modes import AgentMode, TaskStatus
from complex_agent.utils.ids import new_id


@dataclass(slots=True)
class Task:
    id: str
    user_request: str
    normalized_goal: str
    mode: AgentMode
    created_at: datetime
    project_path: Path
    constraints: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.CREATED
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        user_request: str,
        *,
        mode: AgentMode = AgentMode.REVIEW,
        project_path: str | Path = ".",
        constraints: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "Task":
        return cls(
            id=new_id("task"),
            user_request=user_request,
            normalized_goal=" ".join(user_request.strip().split()),
            mode=mode,
            created_at=datetime.now(timezone.utc),
            project_path=Path(project_path).expanduser().resolve(),
            constraints=constraints or {},
            metadata=metadata or {},
        )

