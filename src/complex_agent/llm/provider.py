from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Provider(ABC):
    @abstractmethod
    def complete(self, prompt: str) -> str:
        raise NotImplementedError

    def complete_structured(self, prompt: str, schema_hint: dict[str, Any] | None = None) -> dict[str, Any] | str:
        return self.complete(prompt)
