from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CommandDecision:
    allowed: bool
    requires_approval: bool = False
    reason: str = "allowed"


@dataclass(slots=True)
class CommandGuard:
    allowed_prefixes: tuple[str, ...] = (
        "git status",
        "git diff",
        "git show",
        "git log",
        "rg",
        "pytest",
        "python calculator.py --self-test",
        "python -m pytest",
        "ruff check",
        "mypy",
        "dotnet build",
        "dotnet test",
    )
    approval_prefixes: tuple[str, ...] = (
        "pip install",
        "python -m pip install",
        "npm install",
        "npm update",
        "dotnet add package",
        "ruff format",
        "black",
    )
    blocked_fragments: tuple[str, ...] = (
        "git push",
        "git reset --hard",
        "git clean",
        "rm -rf",
        "del /s",
        "rmdir /s",
        "remove-item -recurse",
        "remove-item",
        "invoke-expression",
        "invoke-webrequest",
        "iex",
        "iwr",
        "curl",
        "powershell",
        "format c:",
        "credential",
    )
    blocked_shell_operators: tuple[str, ...] = ("&&", "||", ";", "|")
    environment_overrides: dict[str, str] = field(default_factory=dict)

    def evaluate(self, command: str) -> CommandDecision:
        normalized = " ".join(command.strip().lower().split())
        if not normalized:
            return CommandDecision(False, reason="Empty command.")
        for fragment in self.blocked_fragments:
            if fragment in normalized:
                return CommandDecision(False, reason=f"Blocked command fragment: {fragment}")
        for operator in self.blocked_shell_operators:
            if operator in command:
                return CommandDecision(False, reason=f"Shell operator is blocked: {operator}")
        if any(normalized.startswith(prefix) for prefix in self.allowed_prefixes):
            return CommandDecision(True)
        if any(normalized.startswith(prefix) for prefix in self.approval_prefixes):
            return CommandDecision(True, requires_approval=True, reason="Command requires approval.")
        return CommandDecision(False, reason=f"Command is not allowlisted: {command}")
