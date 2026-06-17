from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from complex_agent.app import AgentRuntime
from complex_agent.codegen.patch_generator import PatchGenerator
from complex_agent.core.agent_state import AgentState
from complex_agent.core.modes import AgentMode
from complex_agent.core.task import Task
from complex_agent.planning.plan import Plan
from complex_agent.planning.plan_step import PlanStep
from complex_agent.tools.base_tool import ToolContext
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
    proposed_patch: str | None = None
    proposed_files: list[str] = field(default_factory=list)
    proposed_summary: str = ""
    proposed_step_id: str | None = None
    proposed_action: str = "apply_patch"
    verification_output: str = ""
    final_report_text: str = ""
    skill_name: str | None = None


class SessionStore:
    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime
        self.patch_generator = PatchGenerator(runtime.safety)
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
        response = f"План готов: {len(task_session.plan.steps)} шаг(ов)."
        chat.messages.append({"role": "assistant", "content": response})
        return {
            "session_id": chat.id,
            "task_id": task_session.id,
            "messages": chat.messages,
            "assistant_response": response,
            "plan": serialize_plan(task_session.plan),
        }

    def create_plan(self, task_text: str, *, mode: AgentMode) -> TaskSession:
        task = self.runtime.create_task(task_text, mode=mode)
        plan = self.patch_generator.create_plan(task)
        task_session = TaskSession(id=task.id, task=task, plan=plan, status="planned")
        if plan.risks and any("Ollama unavailable" in risk for risk in plan.risks):
            task_session.events.append(
                {
                    "type": "llm_unavailable",
                    "title": "Ollama недоступен",
                    "detail": "; ".join(plan.risks),
                }
            )
        task_session.pending_approvals = self.collect_pending_approvals(task_session)
        self.task_sessions[task_session.id] = task_session
        return task_session

    def get_task(self, task_id: str) -> TaskSession | None:
        return self.task_sessions.get(task_id)

    def propose(self, task_id: str) -> TaskSession | None:
        task_session = self.get_task(task_id)
        if not task_session:
            return None
        task_session.status = "proposing_changes"
        try:
            proposal = self.patch_generator.propose(task_session.task, self.runtime.project_root)
        except Exception as exc:  # noqa: BLE001 - API returns structured task failure
            task_session.status = "failed"
            task_session.events.append(
                {
                    "type": "proposal_failed",
                    "title": "Не удалось предложить изменения",
                    "detail": str(exc),
                }
            )
            return task_session
        task_session.proposed_patch = proposal.patch
        task_session.proposed_files = proposal.changed_files
        task_session.proposed_summary = proposal.summary
        task_session.skill_name = proposal.skill_name
        task_session.proposed_step_id = task_session.proposed_step_id or new_id("step")
        task_session.status = "waiting_approval"
        task_session.events.append(
            {
                "type": "patch_proposed",
                "title": "Предложены изменения",
                "step_id": task_session.proposed_step_id,
                "action": task_session.proposed_action,
            }
        )
        task_session.pending_approvals = self.collect_pending_approvals(task_session)
        return task_session

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
        if task_session.proposed_patch and step_id == task_session.proposed_step_id:
            task_session.status = "approved"
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
        if task_session.proposed_patch:
            return self._run_proposed_patch(task_session)
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

    def _run_proposed_patch(self, task_session: TaskSession) -> TaskSession:
        task_session.pending_approvals = self.collect_pending_approvals(task_session)
        if task_session.pending_approvals:
            task_session.status = "waiting_approval"
            task_session.events.append(
                {"type": "pending_approval", "count": len(task_session.pending_approvals)}
            )
            return task_session

        if not task_session.proposed_patch:
            task_session.status = "failed"
            task_session.events.append({"type": "run_failed", "title": "Нет proposed patch."})
            return task_session

        context = ToolContext(project_root=self.runtime.project_root, safety=self.runtime.safety)
        task_session.status = "applying_patch"
        apply_result = self.runtime.registry.run(
            "apply_patch",
            {"patch": task_session.proposed_patch},
            context,
        )
        task_session.events.append(
            {
                "type": "patch_applied" if apply_result.success else "patch_failed",
                "title": apply_result.summary or apply_result.error or "Patch step finished.",
            }
        )
        if not apply_result.success:
            task_session.status = "failed"
            task_session.final_report_text = _build_calculator_report(
                task_session,
                changed_files=[],
                verification_output="",
                success=False,
                error=apply_result.error or "Patch failed.",
            )
            return task_session

        task_session.status = "verifying"
        verify_result = self.runtime.registry.run(
            "shell",
            {"command": "python calculator.py --self-test", "timeout": 30},
            context,
        )
        task_session.verification_output = verify_result.content or verify_result.error or ""
        task_session.events.append(
            {
                "type": "verification_finished",
                "title": verify_result.summary or "Self-test finished.",
                "status": "completed" if verify_result.success else "failed",
            }
        )
        success = verify_result.success
        task_session.status = "completed" if success else "failed"
        task_session.proposed_files = apply_result.changed_files or task_session.proposed_files
        task_session.final_report_text = _build_calculator_report(
            task_session,
            changed_files=task_session.proposed_files,
            verification_output=task_session.verification_output,
            success=success,
            error=verify_result.error,
        )
        report_path = self.runtime.artifacts.write_text(task_session.final_report_text, suffix=".md")
        task_session.report_path = str(report_path)
        task_session.events.append({"type": "task_finished", "success": success})
        return task_session

    def collect_pending_approvals(self, task_session: TaskSession) -> list[dict[str, Any]]:
        pending: list[dict[str, Any]] = []
        if task_session.proposed_patch and task_session.proposed_step_id:
            key = (task_session.proposed_step_id, task_session.proposed_action)
            if key not in task_session.rejected and not self.runtime.approval_gate.is_approved(
                task_id=task_session.id,
                step_id=task_session.proposed_step_id,
                action=task_session.proposed_action,
            ):
                pending.append(
                    {
                        "step_id": task_session.proposed_step_id,
                        "action": task_session.proposed_action,
                        "description": task_session.proposed_summary or "Применить proposed patch.",
                        "risk": "high",
                        "target": ", ".join(task_session.proposed_files),
                    }
                )
            return pending
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
        "proposed_diff": task_session.proposed_patch or "",
        "proposed_files": list(task_session.proposed_files),
        "proposed_summary": task_session.proposed_summary,
        "verification_output": task_session.verification_output,
        "final_report": task_session.final_report_text,
        "skill_name": task_session.skill_name,
    }


def read_report(path: str | None) -> str:
    if not path:
        return ""
    report_path = Path(path)
    if not report_path.exists() or not report_path.is_file():
        return ""
    return report_path.read_text(encoding="utf-8", errors="replace")


def _build_calculator_report(
    task_session: TaskSession,
    *,
    changed_files: list[str],
    verification_output: str,
    success: bool,
    error: str | None = None,
) -> str:
    lines = [
        "# Готово" if success else "# Завершено с ошибкой",
        "",
        "## Что сделано",
        "- Создан или обновлён calculator.py",
        "- Добавлены операции +, -, *, /",
        "- Добавлена обработка деления на ноль",
        "- Добавлен self-test режим",
        "",
        "## Проверки",
        f"- python calculator.py --self-test: {'успешно' if success else 'ошибка'}",
    ]
    if verification_output:
        lines.extend(["", "```text", verification_output.strip(), "```"])
    if error:
        lines.extend(["", "## Ошибка", f"- {error}"])
    lines.extend(["", "## Изменённые файлы"])
    lines.extend(f"- {path}" for path in changed_files) if changed_files else lines.append("- Нет")
    lines.extend(
        [
            "",
            "## Как запустить",
            "```powershell",
            "python calculator.py",
            "```",
            "",
            "## Как проверить",
            "```powershell",
            "python calculator.py --self-test",
            "```",
        ]
    )
    return "\n".join(lines)
