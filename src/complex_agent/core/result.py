from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Result:
    success: bool
    summary: str
    changed_files: list[str] = field(default_factory=list)
    tests_run: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    final_report: str = ""

