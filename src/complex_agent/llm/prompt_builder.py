from __future__ import annotations


class PromptBuilder:
    def build(self, *, system: str, task: str, context: str = "") -> str:
        return f"{system}\n\nTask:\n{task}\n\nContext:\n{context}".strip()

