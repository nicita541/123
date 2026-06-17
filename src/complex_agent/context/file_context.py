from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FileContext:
    path: str
    snippet: str
    start_line: int = 1

