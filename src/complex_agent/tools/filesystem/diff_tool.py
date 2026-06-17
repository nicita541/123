from __future__ import annotations

import difflib

from complex_agent.core.modes import RiskLevel
from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class DiffTool(BaseTool):
    name = "diff"
    description = "Create a unified diff between two text blobs."
    risk_level = RiskLevel.LOW
    required_keys = ("before", "after")

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        before = str(data["before"]).splitlines(keepends=True)
        after = str(data["after"]).splitlines(keepends=True)
        fromfile = str(data.get("fromfile", "before"))
        tofile = str(data.get("tofile", "after"))
        diff = "".join(difflib.unified_diff(before, after, fromfile=fromfile, tofile=tofile))
        return ToolResult(True, diff, summary="Generated unified diff.")

