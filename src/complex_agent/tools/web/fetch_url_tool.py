from __future__ import annotations

from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class FetchUrlTool(BaseTool):
    name = "fetch_url"
    description = "URL fetching is out of MVP scope."

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        return ToolResult(False, "", error="fetch_url is not implemented in MVP.")

