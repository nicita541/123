from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SkillWorkflow:
    name: str
    when_to_use: str
    tools: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)

