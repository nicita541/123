from __future__ import annotations

from complex_agent.tools.base_tool import ToolContext
from complex_agent.tools.shell.shell_tool import ShellTool
from complex_agent.tools.tool_result import ToolResult


class GitBranchTool(ShellTool):
    name = "git_branch"
    description = "Run git branch --show-current."
    required_keys = ()

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        result = super().run({"command": "git branch --show-current"}, context)
        if not result.success and "not a git repository" in result.content.lower():
            return ToolResult(True, "", summary="Not a git repository; skipped git branch.")
        return result
