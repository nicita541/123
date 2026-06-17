from __future__ import annotations

from complex_agent.llm.provider import Provider


class MockProvider(Provider):
    def complete(self, prompt: str) -> str:
        return "mock response"

