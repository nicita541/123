from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from complex_agent.core.modes import RiskLevel
from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


@dataclass(slots=True)
class _Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str]


@dataclass(slots=True)
class _FilePatch:
    old_path: str
    new_path: str
    hunks: list[_Hunk]


class ApplyPatchTool(BaseTool):
    name = "apply_patch"
    description = "Apply a small unified diff to files inside the project root."
    risk_level = RiskLevel.HIGH
    mutates = True
    required_keys = ("patch",)

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        patch = str(data["patch"])
        if len(patch.encode("utf-8")) > 262_144:
            return ToolResult(False, "", error="Patch exceeds max size.")
        try:
            file_patches = _parse_unified_diff(patch)
            changed = [_apply_file_patch(file_patch, context) for file_patch in file_patches]
        except Exception as exc:  # noqa: BLE001 - tool must return structured errors
            return ToolResult(False, "", error=str(exc))
        return ToolResult(
            True,
            "\n".join(changed),
            summary=f"Applied patch to {len(changed)} files.",
            changed_files=changed,
        )


def _parse_unified_diff(patch: str) -> list[_FilePatch]:
    lines = patch.splitlines()
    patches: list[_FilePatch] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("diff --git "):
            index += 1
            continue
        if not line.startswith("--- "):
            index += 1
            continue
        old_path = _clean_path(line[4:].strip())
        index += 1
        if index >= len(lines) or not lines[index].startswith("+++ "):
            raise ValueError("Invalid unified diff: missing +++ header.")
        new_path = _clean_path(lines[index][4:].strip())
        index += 1
        hunks: list[_Hunk] = []
        while index < len(lines) and lines[index].startswith("@@"):
            match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", lines[index])
            if not match:
                raise ValueError(f"Invalid hunk header: {lines[index]}")
            old_start = int(match.group(1))
            old_count = int(match.group(2) or "1")
            new_start = int(match.group(3))
            new_count = int(match.group(4) or "1")
            index += 1
            hunk_lines: list[str] = []
            while index < len(lines) and not lines[index].startswith(("@@", "--- ")):
                hunk_lines.append(lines[index])
                index += 1
            hunks.append(_Hunk(old_start, old_count, new_start, new_count, hunk_lines))
        patches.append(_FilePatch(old_path, new_path, hunks))
    if not patches:
        raise ValueError("No file patches found.")
    return patches


def _clean_path(path: str) -> str:
    if path == "/dev/null":
        return path
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def _apply_file_patch(file_patch: _FilePatch, context: ToolContext) -> str:
    target_path = file_patch.new_path if file_patch.new_path != "/dev/null" else file_patch.old_path
    if target_path == "/dev/null":
        raise ValueError("Deleting files is not supported by the MVP patch tool.")
    path = context.project_root / target_path
    allowed, reason = context.safety.file_guard.validate_write(path)
    if not allowed:
        raise ValueError(reason)
    original = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
    updated = _apply_hunks(original, file_patch.hunks)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(updated) + ("\n" if updated else ""), encoding="utf-8")
    return path.relative_to(context.project_root).as_posix()


def _apply_hunks(original: list[str], hunks: list[_Hunk]) -> list[str]:
    result: list[str] = []
    cursor = 0
    for hunk in hunks:
        start = max(hunk.old_start - 1, 0)
        if start < cursor:
            raise ValueError("Overlapping hunks are not supported.")
        result.extend(original[cursor:start])
        cursor = start
        for line in hunk.lines:
            if not line:
                continue
            marker = line[0]
            value = line[1:]
            if marker == " ":
                if cursor >= len(original) or original[cursor] != value:
                    raise ValueError(f"Patch context mismatch near line {cursor + 1}.")
                result.append(original[cursor])
                cursor += 1
            elif marker == "-":
                if cursor >= len(original) or original[cursor] != value:
                    raise ValueError(f"Patch removal mismatch near line {cursor + 1}.")
                cursor += 1
            elif marker == "+":
                result.append(value)
            elif line == "\\ No newline at end of file":
                continue
            else:
                raise ValueError(f"Unsupported patch line: {line}")
    result.extend(original[cursor:])
    return result

