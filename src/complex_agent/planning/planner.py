from __future__ import annotations

from complex_agent.context.context_builder import ContextBundle
from complex_agent.core.modes import AgentMode, RiskLevel
from complex_agent.core.task import Task
from complex_agent.planning.plan import Plan
from complex_agent.planning.plan_step import PlanStep


class Planner:
    """Conservative deterministic MVP planner.

    A production planner can swap this with an LLM-backed implementation that still
    returns the same Plan model.
    """

    def create_plan(self, task: Task, context: ContextBundle | None = None) -> Plan:
        steps: list[PlanStep] = []
        if task.mode == AgentMode.CHAT:
            steps.append(
                PlanStep.create(
                    type="respond",
                    description="Answer from available conversation context without tools.",
                    required_tool="final_report",
                    input={"message": task.normalized_goal},
                )
            )
            return Plan.create(task_id=task.id, goal=task.normalized_goal, steps=steps)

        steps.append(
            PlanStep.create(
                type="scan",
                description="Scan project structure and detect stack hints.",
                required_tool="project_scan",
                input={"path": "."},
            )
        )

        if task.mode in {AgentMode.PLAN, AgentMode.REVIEW, AgentMode.DEV, AgentMode.AUTO, AgentMode.AUDIT}:
            steps.append(
                PlanStep.create(
                    type="git_status",
                    description="Capture git status when the project is a git repository.",
                    required_tool="git_status",
                    input={},
                )
            )

        if task.mode in {AgentMode.REVIEW, AgentMode.DEV, AgentMode.AUTO, AgentMode.AUDIT}:
            steps.append(
                PlanStep.create(
                    type="git_diff",
                    description="Capture current diff for review context.",
                    required_tool="git_diff",
                    input={},
                )
            )

        if task.mode == AgentMode.AUDIT:
            steps.append(
                PlanStep.create(
                    type="search",
                    description="Search for common TODO/FIXME markers.",
                    required_tool="search_files",
                    input={"query": "TODO|FIXME", "glob": "*"},
                )
            )

        if task.mode in {AgentMode.DEV, AgentMode.AUTO}:
            steps.append(
                PlanStep.create(
                    type="verify",
                    description="Run the configured safe test command if available.",
                    required_tool="shell",
                    input={"command": "python -m pytest"},
                    risk_level=RiskLevel.MEDIUM,
                    approval_required=task.mode == AgentMode.DEV,
                )
            )

        steps.append(
            PlanStep.create(
                type="final",
                description="Build final report from observations.",
                required_tool="final_report",
                input={"message": task.normalized_goal},
            )
        )
        plan = Plan.create(task_id=task.id, goal=task.normalized_goal, steps=steps)
        if context and context.items:
            plan.risks.append("Context was summarized; inspect relevant files before mutation.")
        return plan

