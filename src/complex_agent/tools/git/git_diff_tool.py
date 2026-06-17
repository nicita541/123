from __future__ import annotations

from complex_agent.tools.base_tool import ToolContext
from complex_agent.tools.shell.shell_tool import ShellTool
from complex_agent.tools.tool_result import ToolResult


class GitDiffTool(ShellTool):
    name = "git_diff"
    description = "Run git diff -- ."
    required_keys = ()

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        result = super().run({"command": "git diff -- ."}, context)
        if not result.success and "not a git repository" in result.content.lower():
            return ToolResult(True, "", summary="Not a git repository; skipped git diff.")
        return result
