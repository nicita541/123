from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Action:
    tool_name: str
    input: dict[str, Any] = field(default_factory=dict)
    description: str = ""

