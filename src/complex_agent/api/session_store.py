from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from complex_agent.app import AgentRuntime
from complex_agent.core.agent_state import AgentState
from complex_agent.core.modes import AgentMode
from complex_agent.core.task import Task
from complex_agent.planning.plan import Plan
from complex_agent.planning.plan_step import PlanStep
from complex_agent.utils.ids import new_id
from complex_agent.utils.json_utils import to_jsonable


@dataclass(slots=True)
class ChatSession:
    id: str
    messages: list[dict[str, str]] = field(default_factory=list)
    current_task_id: str | None = None


@dataclass(slots=True)
class TaskSession:
    id: str
    task: Task
    plan: Plan
    status: str = "planned"
    pending_approvals: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    state: AgentState | None = None
    report_path: str | None = None
    rejected: set[tuple[str, str]] = field(default_factory=set)


class SessionStore:
    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime
        self.chat_sessions: dict[str, ChatSession] = {}
        self.task_sessions: dict[str, TaskSession] = {}

    def get_or_create_chat(self, session_id: str | None = None) -> ChatSession:
        if session_id and session_id in self.chat_sessions:
            return self.chat_sessions[session_id]
        chat = ChatSession(id=session_id or new_id("chat"))
        self.chat_sessions[chat.id] = chat
        return chat

    def chat(self, message: str, *, session_id: str | None, mode: AgentMode) -> dict[str, Any]:
        chat = self.get_or_create_chat(session_id)
        chat.messages.append({"role": "user", "content": message})
        task_session = self.create_plan(message, mode=mode)
        chat.current_task_id = task_session.id
        response = f"Created a {mode.value} plan with {len(task_session.plan.steps)} steps."
        chat.messages.append({"role": "assistant", "content": response})
        return {
            "session_id": chat.id,
            "task_id": task_session.id,
            "messages": chat.messages,
            "assistant_response": response,
            "plan": serialize_plan(task_session.plan),
        }

    def create_plan(self, task_text: str, *, mode: AgentMode) -> TaskSession:
        task, plan = self.runtime.plan(task_text, mode=mode)
        task_session = TaskSession(id=task.id, task=task, plan=plan)
        task_session.pending_approvals = self.collect_pending_approvals(task_session)
        self.task_sessions[task_session.id] = task_session
        return task_session

    def get_task(self, task_id: str) -> TaskSession | None:
        return self.task_sessions.get(task_id)

    def approve(self, task_id: str, *, step_id: str, action: str) -> bool:
        task_session = self.get_task(task_id)
        if not task_session:
            return False
        pending = self.collect_pending_approvals(task_session)
        if not any(item["step_id"] == step_id and item["action"] == action for item in pending):
            return False
        self.runtime.approval_gate.approve(task_id=task_id, step_id=step_id, action=action)
        task_session.pending_approvals = self.collect_pending_approvals(task_session)
        task_session.events.append({"type": "approval_granted", "step_id": step_id, "action": action})
        return True

    def reject(self, task_id: str, *, step_id: str, action: str) -> bool:
        task_session = self.get_task(task_id)
        if not task_session:
            return False
        pending = self.collect_pending_approvals(task_session)
        if not any(item["step_id"] == step_id and item["action"] == action for item in pending):
            return False
        self.runtime.approval_gate.reject(task_id=task_id, step_id=step_id, action=action)
        task_session.rejected.add((step_id, action))
        task_session.pending_approvals = self.collect_pending_approvals(task_session)
        task_session.events.append({"type": "approval_rejected", "step_id": step_id, "action": action})
        task_session.status = "rejected"
        return True

    def run_task(self, task_id: str) -> TaskSession | None:
        task_session = self.get_task(task_id)
        if not task_session:
            return None
        task_session.pending_approvals = self.collect_pending_approvals(task_session)
        if task_session.pending_approvals:
            task_session.status = "pending_approval"
            task_session.events.append(
                {"type": "pending_approval", "count": len(task_session.pending_approvals)}
            )
            return task_session
        state = self.runtime.run_plan(task_session.task, task_session.plan)
        task_session.state = state
        task_session.status = state.task.status.value
        task_session.report_path = state.final_result.final_report if state.final_result else None
        task_session.events.extend(
            to_jsonable(event)
            for event in self.runtime.event_bus.events
            if event.payload.get("task_id") == task_id
        )
        return task_session

    def collect_pending_approvals(self, task_session: TaskSession) -> list[dict[str, Any]]:
        pending: list[dict[str, Any]] = []
        for step in task_session.plan.steps:
            tool = self.runtime.registry.get(step.required_tool)
            if not (tool.mutates or step.approval_required):
                continue
            if (step.id, tool.name) in task_session.rejected:
                continue
            if self.runtime.approval_gate.is_approved(
                task_id=task_session.id,
                step_id=step.id,
                action=tool.name,
            ):
                continue
            pending.append(serialize_approval(step, tool.name, tool.risk_level.value))
        return pending


def parse_mode(value: str) -> AgentMode:
    try:
        return AgentMode(value.lower())
    except ValueError:
        return AgentMode.REVIEW


def serialize_plan(plan: Plan) -> dict[str, Any]:
    return {
        "id": plan.id,
        "task_id": plan.task_id,
        "goal": plan.goal,
        "risks": list(plan.risks),
        "approval_points": list(plan.approval_points),
        "steps": [serialize_step(step) for step in plan.steps],
    }


def serialize_step(step: PlanStep) -> dict[str, Any]:
    return {
        "id": step.id,
        "type": step.type,
        "description": step.description,
        "required_tool": step.required_tool,
        "input": to_jsonable(step.input),
        "risk_level": step.risk_level.value,
        "approval_required": step.approval_required,
        "status": step.status.value,
    }


def serialize_approval(step: PlanStep, action: str, risk: str) -> dict[str, Any]:
    return {
        "step_id": step.id,
        "action": action,
        "description": step.description,
        "risk": risk,
    }


def serialize_task_session(task_session: TaskSession) -> dict[str, Any]:
    state = task_session.state
    return {
        "task_id": task_session.id,
        "status": task_session.status,
        "mode": task_session.task.mode.value,
        "plan": serialize_plan(task_session.plan),
        "pending_approvals": task_session.pending_approvals,
        "events": task_session.events,
        "changed_files": list(state.changed_files) if state else [],
        "errors": list(state.errors) if state else [],
        "warnings": list(state.warnings) if state else [],
        "report_path": task_session.report_path,
    }


def read_report(path: str | None) -> str:
    if not path:
        return ""
    report_path = Path(path)
    if not report_path.exists() or not report_path.is_file():
        return ""
    return report_path.read_text(encoding="utf-8", errors="replace")

