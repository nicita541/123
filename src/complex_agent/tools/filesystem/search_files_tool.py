from __future__ import annotations

import re

from complex_agent.core.modes import RiskLevel
from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class SearchFilesTool(BaseTool):
    name = "search_files"
    description = "Search text in project files after file safety checks."
    risk_level = RiskLevel.LOW
    required_keys = ("query",)

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        query = str(data["query"])
        glob = str(data.get("glob", "*"))
        raw_limit = data.get("limit", 200)
        limit = int(raw_limit) if isinstance(raw_limit, (int, str)) else 200
        return self._run_python(query, glob, limit, context)

    def _run_python(self, query: str, glob: str, limit: int, context: ToolContext) -> ToolResult:
        try:
            pattern = re.compile(query)
        except re.error:
            pattern = re.compile(re.escape(query))
        matches: list[str] = []
        for path in context.project_root.rglob(glob):
            if len(matches) >= limit:
                break
            if not path.is_file():
                continue
            allowed, _ = context.safety.file_guard.validate_read(path)
            if not allowed:
                continue
            try:
                for number, line in enumerate(
                    path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
                ):
                    if pattern.search(line):
                        if context.safety.redact(line) != line:
                            continue
                        rel = path.relative_to(context.project_root).as_posix()
                        matches.append(f"{rel}:{number}:{line}")
                        if len(matches) >= limit:
                            break
            except OSError:
                continue
        content = context.safety.redact("\n".join(matches))
        return ToolResult(True, content, summary=f"Found {len(matches)} matching lines.")
