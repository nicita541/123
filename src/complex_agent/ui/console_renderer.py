from __future__ import annotations

from complex_agent.core.agent_state import AgentState
from complex_agent.planning.plan import Plan


class ConsoleRenderer:
    def render_plan(self, plan: Plan) -> str:
        lines = [f"Plan: {plan.goal}", ""]
        for index, step in enumerate(plan.steps, start=1):
            approval = " approval" if step.approval_required else ""
            lines.append(f"{index}. [{step.required_tool}] {step.description}{approval}")
        return "\n".join(lines)

    def render_state(self, state: AgentState) -> str:
        lines = [
            f"Task: {state.task.normalized_goal}",
            f"Status: {state.task.status.value}",
            "",
            "Observations:",
        ]
        lines.extend(
            f"- {'OK' if obs.success else 'FAIL'} {obs.source}: {obs.summary}"
            for obs in state.observations
        )
        if state.final_result:
            lines.extend(["", f"Report: {state.final_result.final_report}"])
        return "\n".join(lines)

