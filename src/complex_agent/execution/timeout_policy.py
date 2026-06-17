from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TimeoutPolicy:
    seconds: int = 30

