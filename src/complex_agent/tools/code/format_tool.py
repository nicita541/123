from __future__ import annotations

from complex_agent.core.modes import RiskLevel
from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class FormatTool(BaseTool):
    name = "format"
    description = "Formatting is approval-gated and disabled by default in MVP."
    risk_level = RiskLevel.MEDIUM
    mutates = True

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        return ToolResult(False, "", error="format is disabled in MVP; run explicit formatter manually.")

