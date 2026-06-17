from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ContextItem:
    source: str
    content: str
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

