from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from complex_agent.core.modes import AgentMode
from complex_agent.safety.approval_gate import ApprovalGate, ApprovalRequest
from complex_agent.safety.command_guard import CommandDecision, CommandGuard
from complex_agent.safety.file_guard import FileGuard
from complex_agent.safety.secrets_guard import SecretsGuard


@dataclass(slots=True)
class SafetyDecision:
    allowed: bool
    requires_approval: bool = False
    reason: str = "allowed"


class SafetyPolicy:
    def __init__(
        self,
        project_root: str | Path,
        *,
        approval_gate: ApprovalGate | None = None,
        command_guard: CommandGuard | None = None,
        file_guard: FileGuard | None = None,
        secrets_guard: SecretsGuard | None = None,
    ) -> None:
        root = Path(project_root).expanduser().resolve()
        self.project_root = root
        self.approval_gate = approval_gate or ApprovalGate()
        self.command_guard = command_guard or CommandGuard()
        self.file_guard = file_guard or FileGuard(root)
        self.secrets_guard = secrets_guard or SecretsGuard()

    def check_file_read(self, path: str | Path) -> SafetyDecision:
        allowed, reason = self.file_guard.validate_read(path)
        return SafetyDecision(allowed, reason=reason)

    def check_file_write(self, path: str | Path, *, mode: AgentMode) -> SafetyDecision:
        allowed, reason = self.file_guard.validate_write(path)
        if not allowed:
            return SafetyDecision(False, reason=reason)
        requires_approval = mode in {AgentMode.REVIEW, AgentMode.DEV, AgentMode.AUTO}
        return SafetyDecision(True, requires_approval=requires_approval, reason=reason)

    def check_command(self, command: str | Sequence[str]) -> CommandDecision:
        return self.command_guard.evaluate(command)

    def approve_if_needed(
        self,
        *,
        action: str,
        target: str,
        reason: str,
        risk: str,
        task_id: str | None = None,
        step_id: str | None = None,
    ) -> bool:
        return self.approval_gate.require(
            ApprovalRequest(
                action=action,
                target=target,
                reason=reason,
                risk=risk,
                task_id=task_id,
                step_id=step_id,
            )
        )

    def redact(self, text: str) -> str:
        return self.secrets_guard.redact(text)
