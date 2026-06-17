from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from complex_agent.utils.paths import is_relative_to, normalize_path_text


@dataclass(slots=True)
class FileGuard:
    project_root: Path
    forbidden_names: set[str] = field(
        default_factory=lambda: {
            ".env",
            ".env.local",
            "id_rsa",
            "id_ed25519",
            "credentials",
            "credentials.json",
        }
    )
    forbidden_segments: set[str] = field(
        default_factory=lambda: {".git", ".venv", "venv", "node_modules", "__pycache__"}
    )
    forbidden_suffixes: tuple[str, ...] = (".pem", ".key", ".pfx", ".p12")
    max_file_size_bytes: int = 1_048_576

    def resolve(self, path: str | Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.project_root / candidate
        return candidate.resolve()

    def validate_read(self, path: str | Path) -> tuple[bool, str]:
        resolved = self.resolve(path)
        allowed, reason = self._validate_common(resolved)
        if not allowed:
            return False, reason
        if not resolved.exists():
            return False, f"Path does not exist: {resolved}"
        if resolved.is_file() and resolved.stat().st_size > self.max_file_size_bytes:
            return False, f"File exceeds max size: {resolved}"
        return True, "allowed"

    def validate_write(self, path: str | Path) -> tuple[bool, str]:
        resolved = self.resolve(path)
        allowed, reason = self._validate_common(resolved)
        if not allowed:
            return False, reason
        return True, "allowed"

    def _validate_common(self, path: Path) -> tuple[bool, str]:
        if not is_relative_to(path, self.project_root):
            return False, f"Path escapes project root: {path}"
        lowered_parts = {part.lower() for part in path.parts}
        if lowered_parts & self.forbidden_segments:
            return False, f"Path contains forbidden segment: {path}"
        name = path.name.lower()
        if name in self.forbidden_names:
            return False, f"Path is sensitive: {path.name}"
        if name.endswith(self.forbidden_suffixes):
            return False, f"Path has sensitive suffix: {path.name}"
        normalized = normalize_path_text(path)
        if "/secret" in normalized or "/token" in normalized:
            return False, f"Path appears sensitive: {path.name}"
        return True, "allowed"

