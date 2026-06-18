from __future__ import annotations

from complex_agent.tools.base_tool import ToolContext
from complex_agent.tools.shell.shell_tool import ShellTool
from complex_agent.tools.tool_result import ToolResult


class BuildTool(ShellTool):
    name = "build"
    description = "Run a safe build command."
    required_keys: tuple[str, ...] = ()

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        argv = data.get("argv") or ["dotnet", "build"]
        return super().run({"argv": argv, "timeout": data.get("timeout", 120)}, context)
