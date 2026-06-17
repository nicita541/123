from __future__ import annotations

from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class MCPToolAdapter(BaseTool):
    name = "mcp_adapter"
    description = "Placeholder adapter for future MCP tools."

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        return ToolResult(False, "", error="MCP tools are not implemented in MVP.")

