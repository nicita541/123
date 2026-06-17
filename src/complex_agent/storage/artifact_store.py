from __future__ import annotations

from pathlib import Path

from complex_agent.utils.ids import new_id


class ArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write_text(self, text: str, *, suffix: str = ".txt") -> Path:
        path = self.root / f"{new_id('artifact')}{suffix}"
        path.write_text(text, encoding="utf-8")
        return path

