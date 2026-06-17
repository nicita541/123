from __future__ import annotations


class MemorySummarizer:
    def summarize(self, values: list[str], *, max_items: int = 10) -> str:
        return "\n".join(values[-max_items:])

