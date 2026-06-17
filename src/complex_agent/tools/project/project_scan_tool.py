from __future__ import annotations

from collections import Counter

from complex_agent.core.modes import RiskLevel
from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class ProjectScanTool(BaseTool):
    name = "project_scan"
    description = "Scan project files and infer stack hints."
    risk_level = RiskLevel.LOW

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        limit = int(data.get("limit", 500))
        files: list[str] = []
        suffixes: Counter[str] = Counter()
        stack_hints: set[str] = set()
        for path in context.project_root.rglob("*"):
            if len(files) >= limit:
                break
            if not path.is_file():
                continue
            allowed, _ = context.safety.file_guard.validate_read(path)
            if not allowed:
                continue
            rel = path.relative_to(context.project_root).as_posix()
            files.append(rel)
            suffixes[path.suffix.lower() or "<none>"] += 1
            name = path.name.lower()
            if name == "pyproject.toml":
                stack_hints.add("python")
            if name.endswith(".csproj") or name.endswith(".sln"):
                stack_hints.add(".net")
            if path.suffix.lower() == ".xaml":
                stack_hints.add("wpf/xaml")
            if name == "package.json":
                stack_hints.add("javascript")
        content = "\n".join(
            [
                f"root: {context.project_root}",
                f"files_scanned: {len(files)}",
                f"stack_hints: {', '.join(sorted(stack_hints)) or 'unknown'}",
                "top_suffixes:",
                *[f"  {suffix}: {count}" for suffix, count in suffixes.most_common(10)],
                "sample_files:",
                *[f"  {file}" for file in sorted(files)[:50]],
            ]
        )
        return ToolResult(
            True,
            content,
            summary=f"Scanned {len(files)} files.",
            metadata={"files_scanned": len(files), "stack_hints": sorted(stack_hints)},
        )

