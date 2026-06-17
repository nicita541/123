from __future__ import annotations

from typing import Any


class MemoryStore:
    def get(self, key: str, default: Any = None) -> Any:
        raise NotImplementedError

    def set(self, key: str, value: Any) -> None:
        raise NotImplementedError

    def append(self, key: str, value: Any) -> None:
        raise NotImplementedError

    def search(self, query: str) -> list[Any]:
        raise NotImplementedError

    def summarize(self) -> dict[str, Any]:
        raise NotImplementedError

    def clear_task_memory(self) -> None:
        raise NotImplementedError

