from __future__ import annotations


class ModelRouter:
    def route(self, task_type: str) -> str:
        return {
            "planner": "mock",
            "executor": "mock",
            "reviewer": "mock",
            "summarizer": "mock",
            "debugger": "mock",
        }.get(task_type, "mock")

