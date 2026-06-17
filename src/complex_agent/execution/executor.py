from __future__ import annotations

from datetime import datetime, timezone

from complex_agent.core.agent_state import AgentState
from complex_agent.core.modes import AgentMode, StepStatus
from complex_agent.core.step import Step
from complex_agent.events.event_bus import EventBus
from complex_agent.planning.plan import Plan
from complex_agent.tools.base_tool import ToolContext
from complex_agent.tools.registry import ToolRegistry
from complex_agent.tools.tool_result import ToolResult


class Executor:
    def __init__(self, registry: ToolRegistry, tool_context: ToolContext, event_bus: EventBus | None = None):
        self.registry = registry
        self.tool_context = tool_context
        self.event_bus = event_bus or EventBus()

    def execute(self, plan: Plan, state: AgentState) -> AgentState:
        state.current_plan = plan
        for plan_step in plan.steps:
            state.iteration_count += 1
            step = Step(
                id=plan_step.id,
                type=plan_step.type,
                description=plan_step.description,
                required_tool=plan_step.required_tool,
                input=plan_step.input,
                status=StepStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
            )
            self.event_bus.publish(
                "step_started",
                task_id=state.task.id,
                step_id=step.id,
                tool=step.required_tool,
            )
            try:
                result = self._run_step(
                    step,
                    state.task.mode,
                    plan_step.approval_required,
                    task_id=state.task.id,
                )
            except Exception as exc:  # noqa: BLE001 - convert to stateful failure
                result = ToolResult(False, "", error=str(exc), summary=f"{step.required_tool} failed.")
            observation = result.to_observation(step.required_tool)
            state.add_observation(observation)
            state.record_changed_files(result.changed_files)
            step.output = {
                "content": result.content,
                "summary": result.summary,
                "changed_files": result.changed_files,
            }
            step.error = result.error
            step.status = StepStatus.COMPLETED if result.success else StepStatus.FAILED
            step.finished_at = datetime.now(timezone.utc)
            if result.success:
                state.completed_steps.append(step)
            else:
                state.failed_steps.append(step)
            self.event_bus.publish(
                "step_finished",
                task_id=state.task.id,
                step_id=step.id,
                success=result.success,
                error=result.error,
            )
            if not result.success and state.task.mode == AgentMode.AUTO:
                break
        return state

    def _run_step(
        self,
        step: Step,
        mode: AgentMode,
        step_requires_approval: bool,
        *,
        task_id: str,
    ) -> ToolResult:
        tool = self.registry.get(step.required_tool)
        mutation_approved = False
        if tool.mutates:
            if mode == AgentMode.PLAN:
                return ToolResult(False, "", error="Plan mode cannot run mutating tools.")
            approved = self.tool_context.safety.approve_if_needed(
                action=tool.name,
                target=str(step.input),
                reason="Mutating tool requires approval.",
                risk=tool.risk_level.value,
                task_id=task_id,
                step_id=step.id,
            )
            if not approved:
                return ToolResult(False, "", error=f"Mutation rejected for tool: {tool.name}")
            mutation_approved = True
        if step_requires_approval:
            approved = self.tool_context.safety.approve_if_needed(
                action=tool.name,
                target=str(step.input),
                reason="Step requires approval.",
                risk=tool.risk_level.value,
                task_id=task_id,
                step_id=step.id,
            )
            if not approved:
                return ToolResult(False, "", error=f"Approval rejected for tool: {tool.name}")
        self.event_bus.publish("tool_called", tool=tool.name, input=step.input)
        result = self.registry.run(tool.name, step.input, self.tool_context)
        if tool.mutates:
            result.metadata["mutation_approved"] = mutation_approved
        self.event_bus.publish("tool_finished", tool=tool.name, success=result.success)
        return result
