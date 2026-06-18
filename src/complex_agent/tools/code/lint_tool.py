from __future__ import annotations

from complex_agent.tools.base_tool import ToolContext
from complex_agent.tools.shell.shell_tool import ShellTool
from complex_agent.tools.tool_result import ToolResult


class LintTool(ShellTool):
    name = "lint"
    description = "Run a safe lint command."
    required_keys: tuple[str, ...] = ()

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        argv = data.get("argv") or ["ruff", "check", "."]
        return super().run({"argv": argv}, context)
