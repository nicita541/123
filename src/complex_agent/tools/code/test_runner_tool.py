from __future__ import annotations

from complex_agent.tools.base_tool import ToolContext
from complex_agent.tools.shell.shell_tool import ShellTool
from complex_agent.tools.tool_result import ToolResult


class TestRunnerTool(ShellTool):
    name = "test_runner"
    description = "Run a safe test command."
    required_keys = ()

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        return super().run({"command": str(data.get("command") or "python -m pytest")}, context)
