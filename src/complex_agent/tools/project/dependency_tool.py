from __future__ import annotations

from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class DependencyTool(BaseTool):
    name = "dependency_scan"
    description = "Report dependency manifest files."

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        manifests = [
            "pyproject.toml",
            "requirements.txt",
            "package.json",
            "packages.config",
            "Directory.Packages.props",
        ]
        found = [name for name in manifests if (context.project_root / name).exists()]
        return ToolResult(True, "\n".join(found), summary=f"Found {len(found)} dependency manifests.")

