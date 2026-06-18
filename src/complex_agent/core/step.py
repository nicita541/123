from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from complex_agent.core.modes import StepStatus


@dataclass(slots=True)
class Step:
    id: str
    type: str
    description: str
    required_tool: str
    input: dict[str, Any]
    status: StepStatus = StepStatus.PENDING
    output: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
