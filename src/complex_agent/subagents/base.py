from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SubagentResult:
    name: str
    summary: str
    success: bool = True


class Subagent:
    name = "subagent"

    def run(self, task: str) -> SubagentResult:
        return SubagentResult(name=self.name, summary=f"{self.name} is not implemented in MVP.")

