from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ShellSandbox:
    timeout_seconds: int = 30
    capture_output: bool = True

