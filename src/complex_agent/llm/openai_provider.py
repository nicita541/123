from __future__ import annotations

from complex_agent.llm.provider import Provider


class OpenAIProvider(Provider):
    def __init__(self, model: str = "gpt-4.1-mini") -> None:
        self.model = model

    def complete(self, prompt: str) -> str:
        raise NotImplementedError("OpenAIProvider is a placeholder in MVP.")

