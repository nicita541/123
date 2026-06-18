from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppPaths:
    root: Path
    database: Path
    artifacts: Path
    logs: Path
    cache: Path
    config: Path

    @classmethod
    def resolve(cls, override: str | Path | None = None) -> "AppPaths":
        if override is not None:
            root = Path(override).expanduser().resolve()
        elif os.environ.get("COMPLEX_AGENT_DATA_DIR"):
            root = Path(os.environ["COMPLEX_AGENT_DATA_DIR"]).expanduser().resolve()
        elif os.name == "nt" and os.environ.get("LOCALAPPDATA"):
            root = (Path(os.environ["LOCALAPPDATA"]) / "ComplexAgent").resolve()
        else:
            root = (Path.home() / ".complex_agent").resolve()
        return cls(
            root=root,
            database=root / "app.sqlite3",
            artifacts=root / "artifacts",
            logs=root / "logs",
            cache=root / "cache",
            config=root / "config.yaml",
        )

    def ensure(self) -> None:
        for directory in (self.root, self.artifacts, self.logs, self.cache):
            directory.mkdir(parents=True, exist_ok=True)
        if not self.config.exists():
            self.config.write_text(
                "# ComplexAgent local configuration. Runtime settings are stored in app.sqlite3.\n",
                encoding="utf-8",
            )
