from __future__ import annotations

import ntpath
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from complex_agent.app import AgentRuntime
from complex_agent.codegen.patch_generator import PatchGenerator
from complex_agent.core.agent_state import AgentState
from complex_agent.core.modes import AgentMode, RiskLevel, StepStatus, TaskStatus
from complex_agent.core.task import Task
from complex_agent.execution.snapshot_manager import SnapshotManager
from complex_agent.llm.ollama_provider import OllamaProvider, OllamaSettings, load_ollama_settings
from complex_agent.planning.plan import Plan
from complex_agent.planning.plan_step import PlanStep
from complex_agent.safety.project_root_guard import ProjectRootGuard
from complex_agent.storage.app_store import AppStore, utc_now
from complex_agent.tools.base_tool import ToolContext
from complex_agent.tools.filesystem.rollback_tool import RollbackTool
from complex_agent.utils.ids import new_id
from complex_agent.utils.json_utils import to_jsonable


TASK_STATUSES = {
    "draft",
    "planning",
    "planned",
    "proposing",
    "waiting_approval",
    "approved",
    "applying",
    "verifying",
    "needs_fix",
    "completed",
    "failed",
    "rejected",
    "archived",
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "default_access_mode": "review",
    "max_fix_iterations": 3,
    "ui_preferences": {"theme": "dark"},
}


class InvalidTransition(ValueError):
    pass


class RollbackConflict(ValueError):
    pass


@dataclass(slots=True)
class ChatSession:
    id: str
    messages: list[dict[str, str]] = field(default_factory=list)
    current_task_id: str | None = None


@dataclass(slots=True)
class TaskSession:
    id: str
    project_id: str
    task: Task
    plan: Plan
    title: str
    status: str = "planned"
    pending_approvals: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    state: AgentState | None = None
    report_path: str | None = None
    proposed_patch: str | None = None
    proposed_files: list[str] = field(default_factory=list)
    proposed_summary: str = ""
    proposed_step_id: str | None = None
    proposed_action: str = "apply_patch"
    proposal_id: str | None = None
    verification_output: str = ""
    verification_command: str = ""
    final_report_text: str = ""
    skill_name: str | None = None
    fix_iteration: int = 0
    parent_task_id: str | None = None
    created_at: str = ""
    updated_at: str = ""
    rollback_available: bool = False
    rollback_reason: str = ""


class SessionStore:
    def __init__(self, runtime: AgentRuntime, app_store: AppStore | None = None) -> None:
        self.app_store = app_store or AppStore()
        self.project_guard = ProjectRootGuard()
        self.snapshot_manager = SnapshotManager(self.app_store.paths)
        self.runtime = runtime
        self._runtimes: dict[str, AgentRuntime] = {}
        self._generators: dict[str, PatchGenerator] = {}
        self._patch_generator_override: object | None = None
        self.chat_sessions: dict[str, ChatSession] = {}
        self.task_sessions: dict[str, TaskSession] = {}
        self._probe_cache: dict[str, object] | None = None

        root = self._require_project_root(runtime.project_root)
        project = self.app_store.upsert_project(root, default_mode=self.default_mode)
        self.active_project_id = str(project["id"])
        self.app_store.open_project(self.active_project_id)
        self._runtimes[self.active_project_id] = runtime

    @property
    def default_mode(self) -> str:
        return str(self.settings().get("default_access_mode", "review"))

    @property
    def patch_generator(self) -> object:
        return self._patch_generator_override or self._generator_for(self.active_project_id)

    @patch_generator.setter
    def patch_generator(self, value: object) -> None:
        self._patch_generator_override = value

    def _generator_for(self, project_id: str) -> object:
        if self._patch_generator_override is not None:
            return self._patch_generator_override
        if project_id not in self._generators:
            runtime = self._runtime_for_project(project_id)
            base = load_ollama_settings()
            settings = self.settings()
            ollama = OllamaSettings(
                base_url=str(settings.get("ollama_base_url", base.base_url)),
                model=str(settings.get("selected_model", base.model)),
                timeout_seconds=base.timeout_seconds,
                provider="ollama",
                fallback_provider="deterministic",
            )
            self._generators[project_id] = PatchGenerator(runtime.safety, settings=ollama)
        return self._generators[project_id]

    def _runtime_for_project(self, project_id: str) -> AgentRuntime:
        runtime = self._runtimes.get(project_id)
        if runtime is not None:
            return runtime
        project = self.app_store.get_project(project_id)
        if project is None:
            raise ValueError(f"Unknown project: {project_id}")
        root = self._require_project_root(str(project["root_path"]))
        runtime = AgentRuntime(project_path=root, app_data_path=self.app_store.paths.root)
        self._runtimes[project_id] = runtime
        return runtime

    def select_project(self, project_path: str | Path, *, name: str | None = None) -> Path:
        resolved = self._require_project_root(project_path)
        project = self.app_store.upsert_project(resolved, name=name, default_mode=self.default_mode)
        self.active_project_id = str(project["id"])
        self.app_store.open_project(self.active_project_id)
        self.runtime = self._runtime_for_project(self.active_project_id)
        return resolved

    def register_project_mapping(
        self,
        *,
        name: str,
        mount_id: str,
        host_path: str,
        container_path: str,
    ) -> dict[str, Any]:
        configured_root = os.environ.get("AGENT_PROJECTS_ROOT")
        if not configured_root:
            raise ValueError("Project mount registration requires AGENT_PROJECTS_ROOT.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{7,63}", mount_id):
            raise ValueError("Invalid project mount id.")

        allowed_root = Path(configured_root).expanduser().resolve()
        expected_path = (allowed_root / mount_id).resolve()
        requested_path = Path(container_path).expanduser().resolve()
        if requested_path != expected_path:
            raise ValueError(f"Container path must be {expected_path} for this mount id.")
        resolved = self._require_project_root(requested_path)

        existing_mount = self.app_store.get_project_by_mount_id(mount_id)
        if existing_mount and Path(str(existing_mount["root_path"])).resolve() != resolved:
            raise ValueError("Project mount id is already registered for another container path.")

        normalized_host = ntpath.normpath(host_path.strip())
        if (
            not ntpath.isabs(normalized_host)
            or normalized_host == ntpath.splitdrive(normalized_host)[0] + "\\"
        ):
            raise ValueError(
                "Host path metadata must be an absolute project folder, not a drive root."
            )
        if not name.strip():
            raise ValueError("Project name cannot be blank.")

        project = self.app_store.upsert_project(
            resolved,
            name=name.strip(),
            default_mode=self.default_mode,
            mount_id=mount_id,
            host_path=normalized_host,
            container_path=resolved,
        )
        self.active_project_id = str(project["id"])
        self.app_store.open_project(self.active_project_id)
        self.runtime = self._runtime_for_project(self.active_project_id)
        return self.app_store.get_project(self.active_project_id) or project

    def open_project(self, project_id: str) -> dict[str, Any] | None:
        project = self.app_store.get_project(project_id)
        if project is None:
            return None
        self._require_project_root(str(project["root_path"]))
        opened = self.app_store.open_project(project_id)
        self.active_project_id = project_id
        self.runtime = self._runtime_for_project(project_id)
        return opened

    def _require_project_root(self, value: str | Path) -> Path:
        resolved = self.project_guard.require(value)
        app_root = self.app_store.paths.root.resolve()
        if resolved == app_root or app_root in resolved.parents:
            raise ValueError("Application data cannot be selected as a coding project.")
        configured_root = os.environ.get("AGENT_PROJECTS_ROOT")
        if configured_root:
            allowed_root = Path(configured_root).expanduser().resolve()
            if resolved == allowed_root:
                raise ValueError("Choose a project folder below the configured projects root.")
            if allowed_root not in resolved.parents:
                raise ValueError(
                    f"Project must be below the configured projects root: {allowed_root}"
                )
        return resolved

    def archive_project(self, project_id: str) -> bool:
        if project_id == self.active_project_id:
            alternatives = [p for p in self.app_store.list_projects() if p["id"] != project_id]
            if alternatives:
                self.open_project(str(alternatives[0]["id"]))
        return self.app_store.archive_project(project_id)

    def list_projects(
        self, *, include_archived: bool = False, search: str = ""
    ) -> list[dict[str, Any]]:
        return self.app_store.list_projects(include_archived=include_archived, search=search)

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
        self.app_store.add_message(task_session.id, "assistant", response)
        return {
            "session_id": chat.id,
            "task_id": task_session.id,
            "messages": chat.messages,
            "assistant_response": response,
            "plan": serialize_plan(task_session.plan),
        }

    def create_plan(
        self,
        task_text: str,
        *,
        mode: AgentMode,
        project_id: str | None = None,
        parent_task_id: str | None = None,
    ) -> TaskSession:
        selected_project_id = project_id or self.active_project_id
        runtime = self._runtime_for_project(selected_project_id)
        task = runtime.create_task(task_text, mode=mode)
        generator = self._generator_for(selected_project_id)
        model = getattr(getattr(generator, "ollama_provider", None), "model", "")
        title = _task_title(task_text)
        self.app_store.create_task(
            task_id=task.id,
            project_id=selected_project_id,
            parent_task_id=parent_task_id,
            title=title,
            user_message=task_text,
            status="planning",
            mode=mode.value,
            provider="ollama",
            model=str(model),
        )
        self.app_store.add_message(task.id, "user", task_text)
        try:
            plan = generator.create_plan(task)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001 - persist structured planning failure
            plan = _failed_plan(task, exc)
        status = "planned"
        if plan.risks and any("Ollama unavailable" in risk for risk in plan.risks):
            status = "failed"
        self.app_store.add_plan(task.id, plan.id, serialize_plan(plan))
        self.app_store.update_task(task.id, status=status)
        if status == "failed":
            self._record_event(
                task.id,
                {
                    "type": "llm_unavailable",
                    "title": "Ollama недоступен",
                    "detail": "; ".join(plan.risks),
                },
            )
        task_session = self._hydrate_task(task.id)
        if task_session is None:
            raise RuntimeError("Persisted task could not be restored.")
        self.task_sessions[task.id] = task_session
        return task_session

    def continue_task(self, task_id: str, message: str) -> TaskSession | None:
        session = self.get_task(task_id)
        if session is None:
            return None
        if not message.strip():
            raise ValueError("Continuation message cannot be empty.")
        self.app_store.add_message(task_id, "user", message)
        runtime = self._runtime_for_project(session.project_id)
        continuation = runtime.create_task(
            f"Original task: {session.task.user_request}\nContinuation: {message}",
            mode=session.task.mode,
        )
        continuation.id = task_id
        generator = self._generator_for(session.project_id)
        plan = generator.create_plan(continuation)  # type: ignore[attr-defined]
        self.app_store.add_plan(task_id, plan.id, serialize_plan(plan))
        self.app_store.update_task(task_id, status="planned", completed_at=None)
        self._record_event(task_id, {"type": "task_continued", "title": "Задача продолжена"})
        self.task_sessions.pop(task_id, None)
        return self.get_task(task_id)

    def repeat_task(self, task_id: str) -> TaskSession | None:
        session = self.get_task(task_id)
        if session is None:
            return None
        return self.create_plan(
            session.task.user_request,
            mode=session.task.mode,
            project_id=session.project_id,
            parent_task_id=task_id,
        )

    def get_task(self, task_id: str) -> TaskSession | None:
        if task_id in self.task_sessions:
            session = self.task_sessions[task_id]
            session.messages = self.app_store.list_messages(task_id)
            session.events = self.app_store.list_events(task_id)
            session.pending_approvals = self.collect_pending_approvals(session)
            return session
        restored = self._hydrate_task(task_id)
        if restored:
            self.task_sessions[task_id] = restored
        return restored

    def list_tasks(self, project_id: str | None = None) -> list[dict[str, Any]]:
        return self.app_store.list_tasks(project_id or self.active_project_id)

    def propose(self, task_id: str) -> TaskSession | None:
        task_session = self.get_task(task_id)
        if not task_session:
            return None
        if task_session.status not in {"planned", "needs_fix", "failed"}:
            raise InvalidTransition(f"Cannot propose changes while task is {task_session.status}.")
        self.app_store.update_task(task_id, status="proposing")
        runtime = self._runtime_for_project(task_session.project_id)
        generator = self._generator_for(task_session.project_id)
        try:
            proposal = generator.propose(  # type: ignore[attr-defined]
                task_session.task,
                runtime.project_root,
                plan=task_session.plan,
            )
        except Exception as exc:  # noqa: BLE001 - API returns structured task failure
            self.app_store.update_task(task_id, status="failed")
            self._record_event(
                task_id,
                {
                    "type": "proposal_failed",
                    "title": "Не удалось предложить изменения",
                    "detail": str(exc),
                },
            )
            self.task_sessions.pop(task_id, None)
            return self.get_task(task_id)
        return self._persist_proposal(
            task_session, proposal, fix_iteration=task_session.fix_iteration
        )

    def propose_fix(self, task_id: str) -> TaskSession | None:
        task_session = self.get_task(task_id)
        if task_session is None:
            return None
        if task_session.status != "needs_fix":
            raise InvalidTransition("A fix can only be proposed after failed verification.")
        maximum = int(self.settings().get("max_fix_iterations", 3))
        next_iteration = task_session.fix_iteration + 1
        if next_iteration > maximum:
            raise InvalidTransition(f"Maximum fix iterations reached ({maximum}).")
        runtime = self._runtime_for_project(task_session.project_id)
        context = (
            f"Original task:\n{task_session.task.user_request}\n\n"
            f"Last proposed diff:\n{task_session.proposed_patch or ''}\n\n"
            f"Verification failure:\n{task_session.verification_output}\n\n"
            "Propose the smallest safe fix as a new unified diff."
        )
        fix_task = runtime.create_task(context, mode=task_session.task.mode)
        fix_task.id = task_id
        generator = self._generator_for(task_session.project_id)
        try:
            proposal = generator.propose(fix_task, runtime.project_root, plan=task_session.plan)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            self._record_event(
                task_id,
                {
                    "type": "fix_proposal_failed",
                    "title": "Не удалось предложить исправление",
                    "detail": str(exc),
                },
            )
            return self.get_task(task_id)
        self.app_store.update_task(task_id, fix_iteration=next_iteration)
        task_session.fix_iteration = next_iteration
        return self._persist_proposal(task_session, proposal, fix_iteration=next_iteration)

    def _persist_proposal(
        self, task_session: TaskSession, proposal: object, *, fix_iteration: int
    ) -> TaskSession:
        step_id = new_id("step")
        record = self.app_store.add_proposal(
            task_session.id,
            {
                "proposed_diff": getattr(proposal, "patch"),
                "changed_files": getattr(proposal, "changed_files"),
                "summary": getattr(proposal, "summary"),
                "status": "waiting_approval",
                "step_id": step_id,
                "action": "apply_patch",
                "skill_name": getattr(proposal, "skill_name", None),
                "fix_iteration": fix_iteration,
            },
        )
        self.app_store.update_task(task_session.id, status="waiting_approval")
        self._record_event(
            task_session.id,
            {
                "type": "patch_proposed",
                "title": "Предложены изменения",
                "step_id": step_id,
                "action": "apply_patch",
                "proposal_id": record["id"],
            },
        )
        self.task_sessions.pop(task_session.id, None)
        restored = self.get_task(task_session.id)
        if restored is None:
            raise RuntimeError("Persisted proposal could not be restored.")
        return restored

    def approve(self, task_id: str, *, step_id: str, action: str) -> bool:
        task_session = self.get_task(task_id)
        if not task_session:
            return False
        pending = self.collect_pending_approvals(task_session)
        if not any(item["step_id"] == step_id and item["action"] == action for item in pending):
            return False
        self.app_store.add_approval(task_id, step_id, action, "approved")
        runtime = self._runtime_for_project(task_session.project_id)
        runtime.approval_gate.approve(task_id=task_id, step_id=step_id, action=action)
        self.app_store.update_task(task_id, status="approved")
        self._record_event(
            task_id, {"type": "approval_granted", "step_id": step_id, "action": action}
        )
        self.task_sessions.pop(task_id, None)
        return True

    def reject(self, task_id: str, *, step_id: str, action: str) -> bool:
        task_session = self.get_task(task_id)
        if not task_session:
            return False
        pending = self.collect_pending_approvals(task_session)
        if not any(item["step_id"] == step_id and item["action"] == action for item in pending):
            return False
        self.app_store.add_approval(task_id, step_id, action, "rejected")
        self.app_store.update_task(task_id, status="rejected")
        self._record_event(
            task_id, {"type": "approval_rejected", "step_id": step_id, "action": action}
        )
        self.task_sessions.pop(task_id, None)
        return True

    def run_task(self, task_id: str) -> TaskSession | None:
        task_session = self.get_task(task_id)
        if not task_session:
            return None
        if task_session.proposed_patch:
            return self._run_proposed_patch(task_session)
        task_session.pending_approvals = self.collect_pending_approvals(task_session)
        if task_session.pending_approvals:
            task_session.status = "waiting_approval"
            self.app_store.update_task(task_id, status="waiting_approval")
            self._record_event(
                task_id, {"type": "pending_approval", "count": len(task_session.pending_approvals)}
            )
            return task_session
        runtime = self._runtime_for_project(task_session.project_id)
        state = runtime.run_plan(task_session.task, task_session.plan, persist=False)
        task_session.state = state
        status = "completed" if state.final_result and state.final_result.success else "failed"
        task_session.status = status
        task_session.report_path = state.final_result.final_report if state.final_result else None
        report = read_report(task_session.report_path)
        self.app_store.add_run(
            task_id,
            status=status,
            verification_command="",
            verification_argv=[],
            verification_output="",
            report=report,
        )
        self.app_store.update_task(
            task_id,
            status=status,
            completed_at=utc_now() if status == "completed" else None,
        )
        self.task_sessions.pop(task_id, None)
        return self.get_task(task_id)

    def _run_proposed_patch(self, task_session: TaskSession) -> TaskSession:
        task_session.pending_approvals = self.collect_pending_approvals(task_session)
        if task_session.pending_approvals:
            self.app_store.update_task(task_session.id, status="waiting_approval")
            self._record_event(
                task_session.id,
                {"type": "pending_approval", "count": len(task_session.pending_approvals)},
            )
            task_session.status = "waiting_approval"
            return task_session
        if not task_session.proposed_patch or not task_session.proposal_id:
            raise InvalidTransition("Task has no current proposal to run.")

        runtime = self._runtime_for_project(task_session.project_id)
        context = ToolContext(project_root=runtime.project_root, safety=runtime.safety)
        manifest = self.snapshot_manager.capture_before(
            proposal_id=task_session.proposal_id,
            project_root=runtime.project_root,
            relative_paths=task_session.proposed_files,
            safety=runtime.safety,
        )
        self.app_store.update_task(task_session.id, status="applying")
        apply_result = runtime.registry.run(
            "apply_patch", {"patch": task_session.proposed_patch}, context
        )
        self.snapshot_manager.capture_after(manifest, runtime.project_root)
        snapshot_id = self.app_store.add_snapshot(
            task_session.id, task_session.proposal_id, manifest
        )
        self._record_event(
            task_session.id,
            {
                "type": "patch_applied" if apply_result.success else "patch_failed",
                "title": apply_result.summary or apply_result.error or "Patch step finished.",
            },
        )
        if not apply_result.success:
            report = _build_patch_report(
                task_session,
                changed_files=[],
                verification_command="",
                verification_output="",
                success=False,
                error=apply_result.error or "Patch failed.",
            )
            self.app_store.update_proposal(
                task_session.proposal_id, status="failed", snapshot_id=snapshot_id
            )
            self.app_store.add_run(
                task_session.id,
                status="failed",
                verification_command="",
                verification_argv=[],
                verification_output="",
                report=report,
            )
            self.app_store.update_task(task_session.id, status="failed")
            self.task_sessions.pop(task_session.id, None)
            restored = self.get_task(task_session.id)
            if restored is None:
                raise RuntimeError("Failed task could not be restored.")
            return restored

        changed_files = apply_result.changed_files or task_session.proposed_files
        argv = _verification_argv(task_session, changed_files)
        command = _display_command(argv)
        self.app_store.update_proposal(
            task_session.proposal_id,
            status="applied",
            applied_at=utc_now(),
            snapshot_id=snapshot_id,
        )
        self.app_store.update_task(task_session.id, status="verifying")
        if argv:
            verify_result = runtime.registry.run("shell", {"argv": argv, "timeout": 30}, context)
            output = verify_result.content or verify_result.error or verify_result.summary or ""
            success = verify_result.success
            error = verify_result.error
        else:
            output = "Structural verification completed; no allowlisted command was selected."
            success = all((runtime.project_root / path).exists() for path in changed_files)
            error = None if success else "A changed file is missing after patch application."
        status = "completed" if success else "needs_fix"
        self._record_event(
            task_session.id,
            {
                "type": "verification_finished",
                "title": command or "Structural verification",
                "status": status,
            },
        )
        task_session.verification_output = output
        report = _build_patch_report(
            task_session,
            changed_files=changed_files,
            verification_command=command,
            verification_output=output,
            success=success,
            error=error,
        )
        report_path = runtime.artifacts.write_text(report, suffix=".md")
        self.app_store.add_run(
            task_session.id,
            status=status,
            verification_command=command,
            verification_argv=argv,
            verification_output=output,
            report=report,
        )
        self.app_store.update_task(
            task_session.id,
            status=status,
            completed_at=utc_now() if success else None,
        )
        self._record_event(task_session.id, {"type": "task_finished", "success": success})
        self.task_sessions.pop(task_session.id, None)
        restored = self.get_task(task_session.id)
        if restored is None:
            raise RuntimeError("Completed task could not be restored.")
        restored.report_path = str(report_path)
        return restored

    def rollback(self, task_id: str, *, confirm_created_deletions: bool) -> TaskSession | None:
        task_session = self.get_task(task_id)
        if task_session is None:
            return None
        proposal = self.app_store.latest_proposal(task_id, applied_only=True)
        if proposal is None or not proposal.get("snapshot_id"):
            raise InvalidTransition("No applied proposal is available for rollback.")
        snapshot = self.app_store.get_snapshot(str(proposal["snapshot_id"]))
        if snapshot is None or snapshot.get("rolled_back_at"):
            raise InvalidTransition("Rollback snapshot is unavailable.")
        runtime = self._runtime_for_project(task_session.project_id)
        result = RollbackTool(self.app_store.paths).run(
            {
                "manifest": snapshot["manifest"],
                "confirm_created_deletions": confirm_created_deletions,
            },
            ToolContext(runtime.project_root, runtime.safety),
        )
        if not result.success:
            if result.error and "conflict" in result.error.lower():
                raise RollbackConflict(result.error)
            raise InvalidTransition(result.error or "Rollback failed.")
        self.app_store.mark_snapshot_rolled_back(str(snapshot["id"]), str(proposal["id"]))
        self.app_store.update_task(task_id, status="completed", completed_at=utc_now())
        self._record_event(task_id, {"type": "rollback_completed", "title": result.summary})
        self.task_sessions.pop(task_id, None)
        return self.get_task(task_id)

    def collect_pending_approvals(self, task_session: TaskSession) -> list[dict[str, Any]]:
        pending: list[dict[str, Any]] = []
        if task_session.proposed_patch and task_session.proposed_step_id:
            status = self.app_store.approval_status(
                task_session.id, task_session.proposed_step_id, task_session.proposed_action
            )
            if status not in {"approved", "rejected"}:
                pending.append(
                    {
                        "step_id": task_session.proposed_step_id,
                        "action": task_session.proposed_action,
                        "description": task_session.proposed_summary or "Apply proposed patch.",
                        "risk": "high",
                        "target": ", ".join(task_session.proposed_files),
                    }
                )
            return pending
        runtime = self._runtime_for_project(task_session.project_id)
        for step in task_session.plan.steps:
            tool = runtime.registry.get(step.required_tool)
            if not (tool.mutates or step.approval_required):
                continue
            status = self.app_store.approval_status(task_session.id, step.id, tool.name)
            if status not in {"approved", "rejected"}:
                pending.append(serialize_approval(step, tool.name, tool.risk_level.value))
        return pending

    def settings(self) -> dict[str, Any]:
        values = dict(DEFAULT_SETTINGS)
        values.update(self.app_store.get_settings())
        values["app_data_path"] = str(self.app_store.paths.root)
        base = load_ollama_settings()
        values.setdefault("ollama_base_url", base.base_url)
        values.setdefault("selected_model", base.model)
        return values

    def update_settings(self, values: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {
            "ollama_base_url",
            "selected_model",
            "default_access_mode",
            "max_fix_iterations",
            "ui_preferences",
        }
        updates = {key: value for key, value in values.items() if key in allowed}
        if "ollama_base_url" in updates and not str(updates["ollama_base_url"]).startswith(
            ("http://", "https://")
        ):
            raise ValueError("Ollama base URL must use http:// or https://.")
        if "default_access_mode" in updates and updates["default_access_mode"] not in {
            "plan",
            "review",
            "dev",
        }:
            raise ValueError("Unsupported default access mode.")
        if "max_fix_iterations" in updates:
            maximum = int(updates["max_fix_iterations"])
            if maximum < 0 or maximum > 10:
                raise ValueError("max_fix_iterations must be between 0 and 10.")
            updates["max_fix_iterations"] = maximum
        self.app_store.set_settings(updates)
        self._generators.clear()
        self._probe_cache = None
        return self.settings()

    def status_snapshot(self) -> dict[str, object]:
        generator = self.patch_generator
        if not isinstance(generator, PatchGenerator):
            return generator.llm_status()  # type: ignore[attr-defined,no-any-return]
        settings = self.settings()
        cached = self._probe_cache or {}
        return {
            "llm_provider": "ollama",
            "fallback_provider": "deterministic",
            "ollama_base_url": settings["ollama_base_url"],
            "ollama_model": settings["selected_model"],
            "ollama_reachable": bool(cached.get("ollama_reachable", False)),
            "ollama_generation_check": bool(cached.get("ollama_generation_check", False)),
            "ollama_models": cached.get("ollama_models", []),
            "ollama_error": cached.get("ollama_error", "Not probed yet."),
            "demo_fallback_enabled": generator.allow_demo_fallback,
        }

    def probe_ollama(self) -> dict[str, object]:
        settings = self.settings()
        probe_settings = OllamaSettings(
            base_url=str(settings["ollama_base_url"]),
            model=str(settings["selected_model"]),
            timeout_seconds=5,
            provider="ollama",
            fallback_provider="deterministic",
        )
        generator = PatchGenerator(
            self.runtime.safety,
            settings=probe_settings,
            ollama_provider=OllamaProvider.from_settings(probe_settings),
        )
        self._probe_cache = generator.llm_status(include_generation_check=True)
        return self._probe_cache

    def clear_cache(self) -> None:
        for path in self.app_store.paths.cache.iterdir():
            if path.is_file():
                path.unlink()

    def _hydrate_task(self, task_id: str) -> TaskSession | None:
        row = self.app_store.get_task(task_id)
        if row is None:
            return None
        project = self.app_store.get_project(str(row["project_id"]))
        if project is None:
            return None
        mode = parse_mode(str(row["mode"]))
        created = _parse_datetime(str(row["created_at"]))
        task = Task(
            id=str(row["id"]),
            user_request=str(row["user_message"]),
            normalized_goal=" ".join(str(row["user_message"]).strip().split()),
            mode=mode,
            created_at=created,
            project_path=Path(str(project["root_path"])),
            status=TaskStatus.PLANNED,
        )
        plan_row = self.app_store.latest_plan(task_id)
        plan = deserialize_plan(plan_row["plan"] if plan_row else {}, task)
        proposal = self.app_store.latest_proposal(task_id)
        run = self.app_store.latest_run(task_id)
        applied = self.app_store.latest_proposal(task_id, applied_only=True)
        session = TaskSession(
            id=task_id,
            project_id=str(row["project_id"]),
            task=task,
            plan=plan,
            title=str(row["title"]),
            status=str(row["status"]),
            events=self.app_store.list_events(task_id),
            messages=self.app_store.list_messages(task_id),
            proposed_patch=str(proposal["proposed_diff"]) if proposal else None,
            proposed_files=list(proposal["changed_files"]) if proposal else [],
            proposed_summary=str(proposal["summary"]) if proposal else "",
            proposed_step_id=str(proposal["step_id"]) if proposal else None,
            proposed_action=str(proposal["action"]) if proposal else "apply_patch",
            proposal_id=str(proposal["id"]) if proposal else None,
            verification_output=str(run["verification_output"]) if run else "",
            verification_command=str(run["verification_command"]) if run else "",
            final_report_text=str(run["report"]) if run else "",
            skill_name=str(proposal["skill_name"])
            if proposal and proposal.get("skill_name")
            else None,
            fix_iteration=int(row["fix_iteration"]),
            parent_task_id=str(row["parent_task_id"]) if row.get("parent_task_id") else None,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            rollback_available=applied is not None,
            rollback_reason="" if applied else "No applied proposal is available.",
        )
        session.pending_approvals = self.collect_pending_approvals(session)
        return session

    def _record_event(self, task_id: str, event: Mapping[str, Any]) -> None:
        self.app_store.add_event(task_id, event)


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


def deserialize_plan(data: Mapping[str, Any], task: Task) -> Plan:
    raw_steps = data.get("steps", [])
    steps: list[PlanStep] = []
    if isinstance(raw_steps, list):
        for raw in raw_steps:
            if not isinstance(raw, dict):
                continue
            try:
                risk = RiskLevel(str(raw.get("risk_level", "low")))
            except ValueError:
                risk = RiskLevel.LOW
            try:
                status = StepStatus(str(raw.get("status", "pending")))
            except ValueError:
                status = StepStatus.PENDING
            steps.append(
                PlanStep(
                    id=str(raw.get("id") or new_id("step")),
                    type=str(raw.get("type", "step")),
                    description=str(raw.get("description", "")),
                    required_tool=str(raw.get("required_tool", "final_report")),
                    input=dict(raw.get("input", {})) if isinstance(raw.get("input"), dict) else {},
                    risk_level=risk,
                    approval_required=bool(raw.get("approval_required", False)),
                    status=status,
                )
            )
    return Plan(
        id=str(data.get("id") or new_id("plan")),
        task_id=task.id,
        goal=str(data.get("goal") or task.normalized_goal),
        steps=steps,
        risks=[str(value) for value in data.get("risks", [])]
        if isinstance(data.get("risks"), list)
        else [],
        approval_points=[str(value) for value in data.get("approval_points", [])]
        if isinstance(data.get("approval_points"), list)
        else [],
    )


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
        "target": "",
    }


def serialize_task_session(task_session: TaskSession) -> dict[str, Any]:
    state = task_session.state
    return {
        "task_id": task_session.id,
        "project_id": task_session.project_id,
        "parent_task_id": task_session.parent_task_id,
        "title": task_session.title,
        "user_message": task_session.task.user_request,
        "status": task_session.status,
        "mode": task_session.task.mode.value,
        "created_at": task_session.created_at,
        "updated_at": task_session.updated_at,
        "fix_iteration": task_session.fix_iteration,
        "plan": serialize_plan(task_session.plan),
        "messages": task_session.messages,
        "pending_approvals": task_session.pending_approvals,
        "events": task_session.events,
        "changed_files": list(state.changed_files) if state else list(task_session.proposed_files),
        "errors": list(state.errors) if state else [],
        "warnings": list(state.warnings) if state else [],
        "report_path": task_session.report_path,
        "proposed_diff": task_session.proposed_patch or "",
        "proposed_files": list(task_session.proposed_files),
        "proposed_summary": task_session.proposed_summary,
        "verification_command": task_session.verification_command,
        "verification_output": task_session.verification_output,
        "final_report": task_session.final_report_text,
        "skill_name": task_session.skill_name,
        "rollback_available": task_session.rollback_available,
        "rollback_reason": task_session.rollback_reason,
    }


def read_report(path: str | None) -> str:
    if not path:
        return ""
    report_path = Path(path)
    if not report_path.exists() or not report_path.is_file():
        return ""
    return report_path.read_text(encoding="utf-8", errors="replace")


def _verification_argv(task_session: TaskSession, changed_files: Sequence[str]) -> list[str]:
    if task_session.skill_name == "python_calculator":
        return ["python", "calculator.py", "--self-test"]
    py_files = [path.replace("\\", "/") for path in changed_files if path.lower().endswith(".py")]
    if not py_files:
        return []
    return ["python", "-m", "py_compile", *py_files]


def _display_command(argv: Sequence[str]) -> str:
    return " ".join(argv)


def _build_patch_report(
    task_session: TaskSession,
    *,
    changed_files: list[str],
    verification_command: str,
    verification_output: str,
    success: bool,
    error: str | None = None,
) -> str:
    heading = "# Готово" if success else "# Завершено с ошибкой"
    lines = [
        heading,
        "",
        "## Задача",
        task_session.task.normalized_goal,
        "",
        "## Источник изменений",
        "- provider: ollama"
        if task_session.skill_name != "python_calculator"
        else "- provider: deterministic test fallback",
        f"- skill: {task_session.skill_name or 'unknown'}",
        "",
        "## Что сделано",
    ]
    lines.extend(f"- Создан или обновлён `{path}`" for path in changed_files)
    if not changed_files:
        lines.append("- Файлы не были изменены.")
    lines.extend(["", "## Проверки"])
    if verification_command:
        lines.append(f"- `{verification_command}`: {'успешно' if success else 'ошибка'}")
    else:
        lines.append("- Выполнена структурная проверка изменённых файлов.")
    if verification_output:
        lines.extend(["", "```text", verification_output.strip(), "```"])
    if error:
        lines.extend(["", "## Ошибка", f"- {error}"])
    lines.extend(["", "## Изменённые файлы"])
    lines.extend(f"- {path}" for path in changed_files) if changed_files else lines.append("- Нет")
    lines.extend(["", "## Как запустить"])
    if "calculator.py" in changed_files:
        lines.extend(["```powershell", "python calculator.py", "```"])
    elif changed_files:
        lines.append("Запустите изменённые файлы согласно документации проекта.")
    else:
        lines.append("Запуск не требуется.")
    if verification_command:
        lines.extend(["", "## Как проверить", "```powershell", verification_command, "```"])
    return "\n".join(lines)


def _task_title(text: str) -> str:
    normalized = " ".join(text.strip().split())
    return normalized[:80] or "Новая задача"


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)


def _failed_plan(task: Task, exc: Exception) -> Plan:
    plan = Plan.create(
        task_id=task.id,
        goal=task.normalized_goal,
        steps=[
            PlanStep.create(
                type="planning_failed",
                description="Planning failed before any project mutation.",
                required_tool="final_report",
            )
        ],
    )
    plan.risks.append(f"Ollama unavailable: {exc}")
    return plan
