from __future__ import annotations

from complex_agent.tools.base_tool import ToolContext
from complex_agent.tools.registry import ToolRegistry
from complex_agent.tools.tool_result import ToolResult


class ActionRunner:
    def __init__(self, registry: ToolRegistry, context: ToolContext) -> None:
        self.registry = registry
        self.context = context

    def run(self, tool_name: str, data: dict[str, object]) -> ToolResult:
        return self.registry.run(tool_name, data, self.context)

