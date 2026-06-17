from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from complex_agent.core.observation import Observation


@dataclass(slots=True)
class ToolResult:
    success: bool
    content: str
    summary: str = ""
    raw_output: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    changed_files: list[str] = field(default_factory=list)

    def to_observation(self, source: str) -> Observation:
        return Observation(
            source=source,
            content=self.content,
            summary=self.summary or self.content[:200],
            raw_output=self.raw_output,
            success=self.success,
            error=self.error,
            metadata=self.metadata,
        )

