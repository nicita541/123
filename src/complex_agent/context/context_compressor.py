from __future__ import annotations


class ContextCompressor:
    def compress(self, text: str, *, max_chars: int = 4000) -> str:
        if len(text) <= max_chars:
            return text
        head = text[: max_chars // 2]
        tail = text[-max_chars // 2 :]
        return f"{head}\n\n[... truncated ...]\n\n{tail}"

