from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ProjectContext:
    root: str
    files: list[str] = field(default_factory=list)
    stack_hints: list[str] = field(default_factory=list)

