from __future__ import annotations


class AgentError(Exception):
    """Base exception for agent failures."""


class SafetyError(AgentError):
    """Raised when a safety policy blocks an action."""


class ToolError(AgentError):
    """Raised when a tool fails before returning a structured result."""


class PlanValidationError(AgentError):
    """Raised when a plan is invalid."""

