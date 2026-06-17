from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ProjectMemory:
    project_type: str = "unknown"
    important_directories: list[str] = field(default_factory=list)
    build_commands: list[str] = field(default_factory=list)
    test_commands: list[str] = field(default_factory=list)
    conventions: list[str] = field(default_factory=list)

