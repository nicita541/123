from __future__ import annotations

from complex_agent.app import AgentRuntime
from complex_agent.core.modes import AgentMode


runtime = AgentRuntime(project_path=".")
state = runtime.run("Audit this project", mode=AgentMode.AUDIT)
print(state.final_result.summary if state.final_result else "No result")

