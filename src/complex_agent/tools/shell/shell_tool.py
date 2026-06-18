from __future__ import annotations

import subprocess
from collections.abc import Sequence

from complex_agent.core.modes import RiskLevel
from complex_agent.safety.command_guard import display_argv
from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class ShellTool(BaseTool):
    name = "shell"
    description = "Run an allowlisted shell command in the project root."
    risk_level = RiskLevel.MEDIUM
    required_keys: tuple[str, ...] = ("argv",)

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        raw_argv = data.get("argv")
        if raw_argv is None:
            return ToolResult(False, "", error="Shell input requires argv; string commands are rejected.")
        if not isinstance(raw_argv, Sequence) or isinstance(raw_argv, (str, bytes)):
            return ToolResult(False, "", error="Shell input requires argv as a list of strings.")
        argv = [str(value) for value in raw_argv]
        raw_timeout = data.get("timeout", 30)
        timeout = int(raw_timeout) if isinstance(raw_timeout, (int, str)) else 30
        command = display_argv(argv)
        decision = context.safety.check_command(argv)
        if not decision.allowed:
            return ToolResult(False, "", error=decision.reason)
        if decision.requires_approval:
            approved = context.safety.approve_if_needed(
                action="shell",
                target=command,
                reason=decision.reason,
                risk=self.risk_level.value,
            )
            if not approved:
                return ToolResult(False, "", error=f"Command requires approval: {command}")
        try:
            proc = subprocess.run(
                argv,
                cwd=context.project_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            return ToolResult(False, "", error=str(exc))
        except subprocess.TimeoutExpired:
            return ToolResult(False, "", error=f"Command timed out after {timeout}s: {command}")
        raw = "\n".join(part for part in [proc.stdout, proc.stderr] if part)
        redacted = context.safety.redact(raw)
        success = proc.returncode == 0
        return ToolResult(
            success,
            redacted,
            summary=f"Command exited with {proc.returncode}: {command}",
            raw_output=redacted,
            error=None if success else f"Command exited with {proc.returncode}",
            metadata={"returncode": proc.returncode, "command": command, "argv": argv},
        )
