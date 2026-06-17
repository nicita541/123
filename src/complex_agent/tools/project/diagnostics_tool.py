from __future__ import annotations

from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class DiagnosticsTool(BaseTool):
    name = "diagnostics"
    description = "Summarize common diagnostics markers."

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        markers = ["TODO", "FIXME", "HACK", "XXX"]
        counts = dict.fromkeys(markers, 0)
        for path in context.project_root.rglob("*"):
            if not path.is_file():
                continue
            allowed, _ = context.safety.file_guard.validate_read(path)
            if not allowed:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for marker in markers:
                counts[marker] = int(counts[marker]) + text.count(marker)
        content = "\n".join(f"{key}: {value}" for key, value in counts.items())
        return ToolResult(True, content, summary="Collected diagnostics marker counts.")

