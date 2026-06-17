from __future__ import annotations

from complex_agent.safety.approval_gate import ApprovalRequest


class ApprovalUI:
    def prompt(self, request: ApprovalRequest) -> bool:
        answer = input(
            f"Approve {request.action} on {request.target}? Risk={request.risk}. "
            f"Reason={request.reason} [y/N] "
        )
        return answer.strip().lower() in {"y", "yes"}

