from __future__ import annotations

from complex_agent.core.modes import RiskLevel
from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read a text file after file safety checks."
    risk_level = RiskLevel.LOW
    required_keys = ("path",)

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        path = context.project_root / str(data["path"])
        allowed, reason = context.safety.file_guard.validate_read(path)
        if not allowed:
            return ToolResult(False, "", error=reason)
        text = path.read_text(encoding=str(data.get("encoding", "utf-8")), errors="replace")
        text = context.safety.redact(text)
        return ToolResult(True, text, summary=f"Read {path.name}.", metadata={"path": str(path)})

