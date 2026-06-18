from __future__ import annotations

from complex_agent.tools.shell.shell_tool import ShellTool
from complex_agent.tools.base_tool import ToolContext
from complex_agent.tools.tool_result import ToolResult


class GitStatusTool(ShellTool):
    name = "git_status"
    description = "Run git status --short."
    required_keys: tuple[str, ...] = ()

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        result = super().run({"argv": ["git", "status", "--short"]}, context)
        if not result.success and "not a git repository" in result.content.lower():
            return ToolResult(True, "", summary="Not a git repository; skipped git status.")
        return result
