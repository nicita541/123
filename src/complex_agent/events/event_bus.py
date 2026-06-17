from __future__ import annotations

from collections.abc import Callable

from complex_agent.events.events import Event


class EventBus:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self._subscribers: list[Callable[[Event], None]] = []

    def subscribe(self, subscriber: Callable[[Event], None]) -> None:
        self._subscribers.append(subscriber)

    def publish(self, event_type: str, **payload: object) -> Event:
        event = Event(type=event_type, payload=dict(payload))
        self.events.append(event)
        for subscriber in self._subscribers:
            subscriber(event)
        return event

