from __future__ import annotations

from pathlib import Path

from complex_agent.app import AgentRuntime
from complex_agent.core.agent_state import AgentState
from complex_agent.core.modes import AgentMode
from complex_agent.planning.plan import Plan


class AgentLoop:
    def __init__(self, *, project_path: str | Path = ".", auto_approve: bool = False) -> None:
        self.runtime = AgentRuntime(project_path=project_path, auto_approve=auto_approve)

    def plan(self, request: str, *, mode: AgentMode = AgentMode.REVIEW) -> Plan:
        _, plan = self.runtime.plan(request, mode=mode)
        return plan

    def run(self, request: str, *, mode: AgentMode = AgentMode.REVIEW) -> AgentState:
        return self.runtime.run(request, mode=mode)

