from __future__ import annotations

from pathlib import Path

from complex_agent.context.context_builder import ContextBuilder
from complex_agent.core.agent_state import AgentState
from complex_agent.core.modes import AgentMode, TaskStatus
from complex_agent.core.result import Result
from complex_agent.core.task import Task
from complex_agent.events.audit_log import AuditLog
from complex_agent.events.event_bus import EventBus
from complex_agent.events.subscribers import audit_subscriber
from complex_agent.execution.executor import Executor
from complex_agent.planning.plan import Plan
from complex_agent.planning.plan_validator import PlanValidator
from complex_agent.planning.planner import Planner
from complex_agent.review.final_report_builder import FinalReportBuilder
from complex_agent.safety.approval_gate import ApprovalGate
from complex_agent.safety.safety_policy import SafetyPolicy
from complex_agent.storage.artifact_store import ArtifactStore
from complex_agent.storage.app_paths import AppPaths
from complex_agent.storage.run_store import RunStore
from complex_agent.storage.sqlite_store import SQLiteStore
from complex_agent.tools.base_tool import ToolContext
from complex_agent.tools.defaults import create_default_registry
from complex_agent.verification.verifier import Verifier


class AgentRuntime:
    def __init__(
        self,
        *,
        project_path: str | Path = ".",
        auto_approve: bool = False,
        storage_path: str | Path | None = None,
        artifact_path: str | Path | None = None,
        app_data_path: str | Path | None = None,
    ) -> None:
        self.project_root = Path(project_path).expanduser().resolve()
        self.approval_gate = ApprovalGate(auto_approve=auto_approve)
        self.safety = SafetyPolicy(self.project_root, approval_gate=self.approval_gate)
        self.registry = create_default_registry()
        self.context_builder = ContextBuilder()
        self.planner = Planner()
        self.validator = PlanValidator()
        self.report_builder = FinalReportBuilder()
        self.verifier = Verifier(self.safety)
        self.audit_log = AuditLog()
        self.event_bus = EventBus()
        self.event_bus.subscribe(audit_subscriber(self.audit_log))
        app_paths = AppPaths.resolve(app_data_path)
        app_paths.ensure()
        self._storage_path = Path(storage_path or app_paths.cache / "runtime.sqlite3")
        self._artifact_path = Path(artifact_path or app_paths.artifacts / "reports")
        self._sqlite: SQLiteStore | None = None
        self._run_store: RunStore | None = None
        self._artifacts: ArtifactStore | None = None

    @property
    def sqlite(self) -> SQLiteStore:
        if self._sqlite is None:
            self._sqlite = SQLiteStore(self._storage_path)
        return self._sqlite

    @property
    def run_store(self) -> RunStore:
        if self._run_store is None:
            self._run_store = RunStore(self.sqlite)
        return self._run_store

    @property
    def artifacts(self) -> ArtifactStore:
        if self._artifacts is None:
            self._artifacts = ArtifactStore(self._artifact_path)
        return self._artifacts

    def create_task(self, request: str, *, mode: AgentMode) -> Task:
        return Task.create(request, mode=mode, project_path=self.project_root)

    def plan(self, request: str, *, mode: AgentMode = AgentMode.REVIEW) -> tuple[Task, Plan]:
        task = self.create_task(request, mode=mode)
        context = self.context_builder.build_initial_context(task)
        plan = self.planner.create_plan(task, context)
        self.validator.validate(plan)
        task.status = TaskStatus.PLANNED
        self.event_bus.publish("plan_created", task_id=task.id, plan_id=plan.id)
        return task, plan

    def run(self, request: str, *, mode: AgentMode = AgentMode.REVIEW, persist: bool = True) -> AgentState:
        task, plan = self.plan(request, mode=mode)
        return self.run_plan(task, plan, persist=persist)

    def run_plan(self, task: Task, plan: Plan, *, persist: bool = True) -> AgentState:
        state = AgentState(task=task, current_plan=plan)
        task.status = TaskStatus.RUNNING
        self.event_bus.publish("task_started", task_id=task.id, mode=task.mode.value)
        executor = Executor(
            self.registry,
            ToolContext(project_root=self.project_root, safety=self.safety),
            event_bus=self.event_bus,
        )
        executor.execute(plan, state)
        verification = self.verifier.verify_state(state)
        state.errors = verification.errors
        state.warnings = verification.warnings
        task.status = TaskStatus.FAILED if not verification.success else TaskStatus.COMPLETED
        report = self.report_builder.build(state)
        verification = self.verifier.verify_state(state, final_report_text=report)
        state.errors = verification.errors
        state.warnings = verification.warnings
        task.status = TaskStatus.FAILED if not verification.success else TaskStatus.COMPLETED
        report_path = self.artifacts.write_text(report, suffix=".md")
        state.final_result = Result(
            success=verification.success,
            summary="Task completed." if verification.success else "Task completed with errors.",
            changed_files=state.changed_files,
            errors=state.errors,
            warnings=state.warnings,
            next_actions=[] if verification.success else ["Review failed observations."],
            final_report=str(report_path),
        )
        if persist:
            self.run_store.save_state(state)
        self.event_bus.publish("task_finished", task_id=task.id, success=state.final_result.success)
        return state
