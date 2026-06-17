from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from complex_agent.core.modes import RiskLevel
from complex_agent.safety.safety_policy import SafetyPolicy
from complex_agent.tools.tool_result import ToolResult


@dataclass(slots=True)
class ToolContext:
    project_root: Path
    safety: SafetyPolicy


class BaseTool(ABC):
    name: str
    description: str
    risk_level: RiskLevel = RiskLevel.LOW
    mutates: bool = False
    availability: str = "enabled"
    required_keys: tuple[str, ...] = ()

    def validate_input(self, data: dict[str, Any]) -> None:
        missing = [key for key in self.required_keys if key not in data]
        if missing:
            raise ValueError(f"Missing required input keys for {self.name}: {', '.join(missing)}")

    @abstractmethod
    def run(self, data: dict[str, Any], context: ToolContext) -> ToolResult:
        raise NotImplementedError
