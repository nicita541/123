from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

from complex_agent.safety.safety_policy import SafetyPolicy
from complex_agent.storage.app_paths import AppPaths


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SnapshotManager:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def capture_before(
        self,
        *,
        proposal_id: str,
        project_root: Path,
        relative_paths: Iterable[str],
        safety: SafetyPolicy,
    ) -> dict[str, Any]:
        snapshot_root = self.paths.artifacts / "snapshots" / proposal_id
        snapshot_root.mkdir(parents=True, exist_ok=True)
        files: list[dict[str, Any]] = []
        for index, relative in enumerate(dict.fromkeys(relative_paths)):
            normalized = relative.replace("\\", "/")
            target = (project_root / normalized).resolve()
            allowed, reason = safety.file_guard.validate_write(target)
            if not allowed:
                raise ValueError(reason)
            existed = target.exists()
            backup_relative: str | None = None
            if existed:
                backup = snapshot_root / f"{index}.bin"
                backup.write_bytes(target.read_bytes())
                backup_relative = backup.relative_to(self.paths.root).as_posix()
            files.append(
                {
                    "path": normalized,
                    "existed": existed,
                    "backup": backup_relative,
                    "before_sha256": file_sha256(target),
                    "post_sha256": None,
                }
            )
        return {"version": 1, "proposal_id": proposal_id, "files": files}

    @staticmethod
    def capture_after(manifest: dict[str, Any], project_root: Path) -> dict[str, Any]:
        for item in manifest.get("files", []):
            if isinstance(item, dict):
                item["post_sha256"] = file_sha256(project_root / str(item.get("path", "")))
        return manifest
