from __future__ import annotations

from complex_agent.events.audit_log import AuditLog
from complex_agent.events.events import Event


def audit_subscriber(audit_log: AuditLog):
    def _subscriber(event: Event) -> None:
        audit_log.record(event)

    return _subscriber

