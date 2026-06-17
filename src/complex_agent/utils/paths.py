from __future__ import annotations

from pathlib import Path


def resolve_project_path(path: str | Path | None = None) -> Path:
    return Path(path or ".").expanduser().resolve()


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def normalize_path_text(path: str | Path) -> str:
    return str(path).replace("\\", "/").lower()

