from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Sequence


@dataclass(slots=True)
class CommandDecision:
    allowed: bool
    requires_approval: bool = False
    reason: str = "allowed"


def parse_command_argv(command: str) -> list[str]:
    if any(operator in command for operator in ("&&", "||", ";", "|", "\n", "\r")):
        raise ValueError("Shell operators are not allowed.")
    try:
        argv = shlex.split(command, posix=True)
    except ValueError as exc:
        raise ValueError(f"Invalid command quoting: {exc}") from exc
    if not argv:
        raise ValueError("Empty command.")
    return argv


def display_argv(argv: Sequence[str]) -> str:
    return " ".join(shlex.quote(value) for value in argv)


@dataclass(slots=True)
class CommandGuard:
    allowed_prefixes: tuple[tuple[str, ...], ...] = (
        ("git", "status"),
        ("git", "diff"),
        ("git", "show"),
        ("git", "log"),
        ("git", "branch", "--show-current"),
        ("rg",),
        ("pytest",),
        ("python", "calculator.py", "--self-test"),
        ("python", "-m", "py_compile"),
        ("python", "-m", "pytest"),
        ("ruff", "check"),
        ("mypy",),
        ("dotnet", "build"),
        ("dotnet", "test"),
    )
    approval_prefixes: tuple[tuple[str, ...], ...] = (
        ("pip", "install"),
        ("python", "-m", "pip", "install"),
        ("npm", "install"),
        ("npm", "update"),
        ("dotnet", "add", "package"),
        ("ruff", "format"),
        ("black",),
    )
    blocked_tokens: set[str] = field(
        default_factory=lambda: {
            "powershell",
            "pwsh",
            "cmd",
            "curl",
            "iwr",
            "iex",
            "invoke-expression",
            "invoke-webrequest",
        }
    )
    environment_overrides: dict[str, str] = field(default_factory=dict)

    def evaluate(self, command: str | Sequence[str]) -> CommandDecision:
        try:
            argv = parse_command_argv(command) if isinstance(command, str) else [str(v) for v in command]
        except ValueError as exc:
            return CommandDecision(False, reason=str(exc))
        if not argv or any(not value or "\x00" in value for value in argv):
            return CommandDecision(False, reason="Command argv is empty or invalid.")
        lowered = tuple(value.lower() for value in argv)
        if any(token in self.blocked_tokens for token in lowered):
            return CommandDecision(False, reason="Blocked command executable or argument.")
        if lowered[:2] == ("git", "push") or lowered[:3] == ("git", "reset", "--hard"):
            return CommandDecision(False, reason="Dangerous git command is blocked.")
        if lowered[:2] == ("git", "clean") or lowered[:2] in {("rm", "-rf"), ("del", "/s")}:
            return CommandDecision(False, reason="Destructive command is blocked.")
        if lowered and lowered[0] in {"remove-item", "rmdir", "format"}:
            return CommandDecision(False, reason="Destructive command is blocked.")
        if any(self._starts_with(lowered, prefix) for prefix in self.allowed_prefixes):
            return CommandDecision(True)
        if any(self._starts_with(lowered, prefix) for prefix in self.approval_prefixes):
            return CommandDecision(True, requires_approval=True, reason="Command requires approval.")
        return CommandDecision(False, reason=f"Command is not allowlisted: {display_argv(argv)}")

    @staticmethod
    def _starts_with(argv: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
        return len(argv) >= len(prefix) and argv[: len(prefix)] == prefix
