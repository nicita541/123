from __future__ import annotations


class TaskDecomposer:
    def decompose(self, request: str) -> list[str]:
        parts = [part.strip() for part in request.replace("\n", ". ").split(".") if part.strip()]
        return parts or [request.strip()]

