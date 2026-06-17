from __future__ import annotations

from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Web search is out of MVP scope."

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        return ToolResult(False, "", error="web_search is not implemented in MVP.")

