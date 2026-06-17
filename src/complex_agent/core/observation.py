from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Observation:
    source: str
    content: str
    summary: str
    raw_output: str | None
    success: bool
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

