from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PermissionManager:
    allow_mutation: bool = False
    allow_shell: bool = True

