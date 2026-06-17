from __future__ import annotations

from complex_agent.core.agent_state import AgentState
from complex_agent.planning.plan import Plan
from complex_agent.planning.plan_step import PlanStep


class Replanner:
    def replan_after_failure(self, state: AgentState) -> Plan:
        state.replan_count += 1
        failed = state.failed_steps[-1].description if state.failed_steps else "unknown step"
        step = PlanStep.create(
            type="final",
            description="Report failure and recommend manual intervention.",
            required_tool="final_report",
            input={"message": f"Execution failed after: {failed}"},
        )
        return Plan.create(task_id=state.task.id, goal=state.task.normalized_goal, steps=[step])

