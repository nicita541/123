from __future__ import annotations

from complex_agent.core.agent_state import AgentState
from complex_agent.core.modes import RiskLevel
from complex_agent.tools.base_tool import BaseTool, ToolContext
from complex_agent.tools.tool_result import ToolResult


class FinalReportBuilder:
    def build(self, state: AgentState) -> str:
        lines = [
            "# Final Report",
            "",
            f"Task: {state.task.normalized_goal}",
            f"Mode: {state.task.mode.value}",
            f"Status: {state.task.status.value}",
            "",
            "## Observations",
        ]
        if state.observations:
            lines.extend(
                f"- {'OK' if obs.success else 'FAIL'} {obs.source}: {obs.summary}"
                for obs in state.observations
            )
        else:
            lines.append("- No observations recorded.")
        lines.extend(["", "## Changed Files"])
        lines.extend(f"- {path}" for path in state.changed_files) if state.changed_files else lines.append(
            "- None"
        )
        lines.extend(["", "## Errors"])
        lines.extend(f"- {error}" for error in state.errors) if state.errors else lines.append("- None")
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in state.warnings) if state.warnings else lines.append(
            "- None"
        )
        return "\n".join(lines)


class FinalReportTool(BaseTool):
    name = "final_report"
    description = "Return a simple report placeholder for tool-only final steps."
    risk_level = RiskLevel.LOW
    availability = "internal"

    def run(self, data: dict[str, object], context: ToolContext) -> ToolResult:
        message = str(data.get("message", "Task completed."))
        return ToolResult(True, message, summary="Final report step completed.")
