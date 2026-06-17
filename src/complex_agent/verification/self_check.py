from __future__ import annotations

from complex_agent.core.agent_state import AgentState


class SelfCheck:
    def check(self, state: AgentState) -> list[str]:
        if state.errors:
            return ["Execution completed with errors."]
        return []

