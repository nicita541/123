from __future__ import annotations

from pathlib import Path

from complex_agent.core.modes import RiskLevel
from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class ListFilesTool(BaseTool):
    name = "list_files"
    description = "List project files while skipping denied paths."
    risk_level = RiskLevel.LOW

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        pattern = str(data.get("pattern", "*"))
        limit = int(data.get("limit", 200))
        root = context.project_root / str(data.get("path", "."))
        root = root.resolve()
        allowed, reason = context.safety.file_guard.validate_read(root)
        if not allowed:
            return ToolResult(False, "", error=reason)
        files: list[str] = []
        for path in root.rglob(pattern):
            if len(files) >= limit:
                break
            if not path.is_file():
                continue
            rel = _relative(path, context.project_root)
            allowed, _ = context.safety.file_guard.validate_read(path)
            if allowed:
                files.append(rel)
        content = "\n".join(sorted(files))
        return ToolResult(True, content, summary=f"Listed {len(files)} files.", metadata={"count": len(files)})


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()

