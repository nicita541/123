from __future__ import annotations

from dataclasses import dataclass, field

from complex_agent.events.events import Event


@dataclass(slots=True)
class AuditLog:
    records: list[Event] = field(default_factory=list)

    def record(self, event: Event) -> None:
        self.records.append(event)

