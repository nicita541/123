from __future__ import annotations

from typing import Any

from complex_agent.llm.mock_provider import MockProvider
from complex_agent.llm.provider import Provider


class LLMClient:
    def __init__(self, provider: Provider | None = None) -> None:
        self.provider = provider or MockProvider()

    def complete(self, prompt: str) -> str:
        return self.provider.complete(prompt)

    def complete_structured(self, prompt: str, schema: type[Any] | None = None) -> dict[str, Any]:
        return {"content": self.complete(prompt), "schema": getattr(schema, "__name__", None)}

    def stream(self, prompt: str) -> list[str]:
        return [self.complete(prompt)]

    def count_tokens(self, text: str) -> int:
        return max(1, len(text.split()))

