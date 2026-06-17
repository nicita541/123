from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ConversationContext:
    messages: list[str] = field(default_factory=list)

