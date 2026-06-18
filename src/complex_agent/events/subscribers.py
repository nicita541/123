from __future__ import annotations

from collections.abc import Callable

from complex_agent.events.audit_log import AuditLog
from complex_agent.events.events import Event


def audit_subscriber(audit_log: AuditLog) -> Callable[[Event], None]:
    def _subscriber(event: Event) -> None:
        audit_log.record(event)

    return _subscriber
