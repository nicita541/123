from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProjectRootDecision:
    allowed: bool
    path: Path
    reason: str = "allowed"
    warning: str | None = None


class ProjectRootGuard:
    """Reject roots whose blast radius is too broad for a coding-agent sandbox."""

    def evaluate(self, value: str | Path, *, require_exists: bool = True) -> ProjectRootDecision:
        path = Path(value).expanduser().resolve()
        if require_exists and (not path.exists() or not path.is_dir()):
            return ProjectRootDecision(False, path, f"Project folder does not exist: {path}")
        if path == Path(path.anchor):
            return ProjectRootDecision(
                False,
                path,
                "Choose a specific project folder, not an entire drive or filesystem root.",
            )
        home = Path.home().resolve()
        if path == home:
            return ProjectRootDecision(False, path, "The entire user home cannot be a project root.")

        blocked = self._blocked_system_directories()
        if path in blocked:
            return ProjectRootDecision(False, path, f"System directory cannot be a project root: {path}")

        warning = None
        desktop = (home / "Desktop").resolve()
        if path == desktop:
            warning = "Selecting the entire Desktop is discouraged; prefer a project subfolder."
        return ProjectRootDecision(True, path, warning=warning)

    @staticmethod
    def _blocked_system_directories() -> set[Path]:
        values: set[Path] = set()
        if os.name == "nt":
            for name in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
                raw = os.environ.get(name)
                if raw:
                    values.add(Path(raw).resolve())
        else:
            values.update(Path(path) for path in ("/bin", "/boot", "/etc", "/sbin", "/usr", "/var"))
        return values

    def require(self, value: str | Path, *, require_exists: bool = True) -> Path:
        decision = self.evaluate(value, require_exists=require_exists)
        if not decision.allowed:
            raise ValueError(decision.reason)
        return decision.path
