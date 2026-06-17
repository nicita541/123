from __future__ import annotations

from complex_agent.core.modes import RiskLevel
from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class GitCommitTool(BaseTool):
    name = "git_commit"
    description = "Disabled in MVP; auto-commit is out of scope."
    risk_level = RiskLevel.CRITICAL
    mutates = True
    availability = "disabled"

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        return ToolResult(False, "", error="git_commit is disabled in MVP.")
