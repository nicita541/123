from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TokenBudget:
    max_tokens: int = 4000

    def remaining(self, used: int) -> int:
        return max(0, self.max_tokens - used)

