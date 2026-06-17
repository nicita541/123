from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ApprovalRequest:
    action: str
    target: str
    reason: str
    risk: str
    task_id: str | None = None
    step_id: str | None = None


class ApprovalGate:
    def __init__(self, *, auto_approve: bool = False) -> None:
        self.auto_approve = auto_approve
        self.decisions: list[ApprovalRequest] = []
        self._approved: set[tuple[str | None, str | None, str]] = set()
        self._rejected: set[tuple[str | None, str | None, str]] = set()

    def require(self, request: ApprovalRequest) -> bool:
        self.decisions.append(request)
        key = self._key(request.task_id, request.step_id, request.action)
        if key in self._rejected:
            return False
        return self.auto_approve or key in self._approved

    def approve(self, *, task_id: str | None, step_id: str | None, action: str) -> None:
        key = self._key(task_id, step_id, action)
        self._rejected.discard(key)
        self._approved.add(key)

    def reject(self, *, task_id: str | None, step_id: str | None, action: str) -> None:
        key = self._key(task_id, step_id, action)
        self._approved.discard(key)
        self._rejected.add(key)

    def is_approved(self, *, task_id: str | None, step_id: str | None, action: str) -> bool:
        return self._key(task_id, step_id, action) in self._approved

    @staticmethod
    def _key(task_id: str | None, step_id: str | None, action: str) -> tuple[str | None, str | None, str]:
        return task_id, step_id, action
