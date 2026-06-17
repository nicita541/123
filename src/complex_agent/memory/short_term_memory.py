from __future__ import annotations

from typing import Any

from complex_agent.memory.memory_store import MemoryStore


class ShortTermMemory(MemoryStore):
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def append(self, key: str, value: Any) -> None:
        self._data.setdefault(key, []).append(value)

    def search(self, query: str) -> list[Any]:
        return [value for key, value in self._data.items() if query.lower() in key.lower()]

    def summarize(self) -> dict[str, Any]:
        return dict(self._data)

    def clear_task_memory(self) -> None:
        self._data.clear()

