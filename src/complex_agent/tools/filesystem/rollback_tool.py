from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from complex_agent.core.modes import RiskLevel
from complex_agent.execution.snapshot_manager import file_sha256
from complex_agent.storage.app_paths import AppPaths
from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class RollbackTool(BaseTool):
    name = "rollback"
    description = "Restore an approved patch snapshot inside the task project root."
    risk_level = RiskLevel.HIGH
    mutates = True
    required_keys = ("manifest", "confirm_created_deletions")

    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        manifest = data.get("manifest")
        if not isinstance(manifest, dict):
            return ToolResult(False, "", error="Rollback manifest is invalid.")
        confirm_deletions = data.get("confirm_created_deletions") is True
        try:
            items = self._validate(manifest, context, confirm_deletions=confirm_deletions)
            changed = self._restore(items, context)
        except (OSError, ValueError) as exc:
            return ToolResult(False, "", error=str(exc))
        return ToolResult(
            True,
            "\n".join(changed),
            summary=f"Rolled back {len(changed)} file(s).",
            changed_files=changed,
        )

    def _validate(
        self,
        manifest: dict[str, Any],
        context: ToolContext,
        *,
        confirm_deletions: bool,
    ) -> list[tuple[dict[str, Any], Path]]:
        raw_files = manifest.get("files")
        if not isinstance(raw_files, list) or not raw_files:
            raise ValueError("Rollback snapshot contains no files.")
        items: list[tuple[dict[str, Any], Path]] = []
        for raw in raw_files:
            if not isinstance(raw, dict):
                raise ValueError("Rollback snapshot contains an invalid file entry.")
            relative = str(raw.get("path", ""))
            target = (context.project_root / relative).resolve()
            allowed, reason = context.safety.file_guard.validate_write(target)
            if not allowed:
                raise ValueError(reason)
            expected = raw.get("post_sha256")
            current = file_sha256(target)
            if current != expected:
                raise ValueError(
                    f"Rollback conflict for {relative}: the file changed after the agent patch."
                )
            if not bool(raw.get("existed")) and not confirm_deletions:
                raise ValueError(
                    "Rollback would delete agent-created files; explicit confirmation is required."
                )
            backup = raw.get("backup")
            if bool(raw.get("existed")):
                if not isinstance(backup, str):
                    raise ValueError(f"Rollback backup is missing for {relative}.")
                backup_path = (self.paths.root / backup).resolve()
                if self.paths.root not in backup_path.parents:
                    raise ValueError("Rollback backup path escapes application storage.")
                if not backup_path.is_file():
                    raise ValueError(f"Rollback backup is unavailable for {relative}.")
            items.append((raw, target))
        return items

    def _restore(
        self, items: list[tuple[dict[str, Any], Path]], context: ToolContext
    ) -> list[str]:
        changed: list[str] = []
        for raw, target in items:
            relative = str(raw["path"])
            if bool(raw.get("existed")):
                backup_path = self.paths.root / str(raw["backup"])
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(f".{target.name}.rollback.tmp")
                temporary.write_bytes(backup_path.read_bytes())
                os.replace(temporary, target)
            elif target.exists():
                target.unlink()
            changed.append(relative)
        return changed
