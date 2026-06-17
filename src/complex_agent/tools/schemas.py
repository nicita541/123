from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolSchema:
    name: str
    required_keys: tuple[str, ...] = ()
    mutates: bool = False

