from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response

from complex_agent.api.schemas import (
    ApprovalRequestModel,
    ChatRequest,
    ContinueTaskRequest,
    FileListResponse,
    FilePreviewResponse,
    GitDiffResponse,
    PlanRequest,
    ProjectCreateRequest,
    ProjectRegistrationRequest,
    ProjectResponse,
    ProjectSelectRequest,
    RollbackRequest,
    SettingsUpdateRequest,
    TimelineResponse,
    WorkspaceResponse,
)
from complex_agent.api.session_store import (
    InvalidTransition,
    RollbackConflict,
    SessionStore,
    parse_mode,
    serialize_task_session,
)
from complex_agent.tools.base_tool import ToolContext


def create_router(store: SessionStore) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "local_only": True}

    @router.get("/api/status")
    def status() -> dict[str, Any]:
        llm_status = store.status_snapshot()
        return {
            "project_id": store.active_project_id,
            "project_root": str(store.runtime.project_root),
            "mode": store.default_mode,
            "tool_count": len(store.runtime.registry.list_tools()),
            "agent_state_exists": False,
            "latest_run": _latest_run_summary(store),
            **llm_status,
        }

    @router.post("/api/ollama/probe")
    def probe_ollama() -> dict[str, object]:
        return store.probe_ollama()

    @router.get("/api/tools")
    def tools() -> dict[str, Any]:
        return {"tools": store.runtime.registry.list_tool_info(include_all=True)}

    @router.get("/api/projects")
    def projects(
        include_archived: bool = False,
        search: str = Query(default="", max_length=200),
    ) -> dict[str, Any]:
        return {
            "projects": [
                _project_public(project, active_id=store.active_project_id)
                for project in store.list_projects(include_archived=include_archived, search=search)
            ]
        }

    @router.post("/api/projects")
    def create_project(payload: ProjectCreateRequest) -> dict[str, Any]:
        if os.environ.get("AGENT_PROJECTS_ROOT"):
            raise HTTPException(
                status_code=400,
                detail="Use /api/projects/register when project mounts are enabled.",
            )
        try:
            store.select_project(payload.root_path, name=payload.name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        project = store.app_store.get_project(store.active_project_id)
        if project is None:
            raise HTTPException(status_code=500, detail="Project was not persisted.")
        return _project_public(project, active_id=store.active_project_id)

    @router.post("/api/projects/register")
    def register_project(payload: ProjectRegistrationRequest) -> dict[str, Any]:
        try:
            project = store.register_project_mapping(
                name=payload.name,
                mount_id=payload.mount_id,
                host_path=payload.host_path,
                container_path=payload.container_path,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _project_public(project, active_id=store.active_project_id)

    @router.get("/api/projects/{project_id}")
    def get_project_by_id(project_id: str) -> dict[str, Any]:
        project = store.app_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Unknown project.")
        return _project_public(project, active_id=store.active_project_id)

    @router.post("/api/projects/{project_id}/open")
    def open_project(project_id: str) -> dict[str, Any]:
        try:
            project = store.open_project(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if project is None:
            raise HTTPException(status_code=404, detail="Unknown project.")
        return _project_public(project, active_id=store.active_project_id)

    @router.post("/api/projects/{project_id}/archive")
    def archive_project(project_id: str) -> dict[str, Any]:
        if not store.archive_project(project_id):
            raise HTTPException(status_code=404, detail="Unknown project.")
        return {
            "project_id": project_id,
            "archived": True,
            "active_project_id": store.active_project_id,
        }

    @router.get("/api/project", response_model=ProjectResponse)
    def get_project() -> dict[str, Any]:
        return _project_response(store)

    @router.post("/api/project/select", response_model=ProjectResponse)
    def select_project(payload: ProjectSelectRequest) -> dict[str, Any]:
        if os.environ.get("AGENT_PROJECTS_ROOT"):
            raise HTTPException(
                status_code=400,
                detail="Open a registered project by id when project mounts are enabled.",
            )
        try:
            store.select_project(payload.path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _project_response(store)

    @router.get("/api/workspace", response_model=WorkspaceResponse)
    def workspace() -> dict[str, Any]:
        files = _safe_file_items(store, limit=300)
        changed_files = _changed_files(store)
        return {
            "project_root": str(store.runtime.project_root),
            "git_branch": _git_branch(store),
            "important_directories": _important_directories(store),
            "files": files[:80],
            "changed_files": changed_files,
            "tool_count": len(store.runtime.registry.list_tool_info(include_all=True)),
            "enabled_tool_count": len(store.runtime.registry.list_tools()),
            "status": "ready",
        }

    @router.get("/api/files", response_model=FileListResponse)
    def files(limit: int = Query(default=500, ge=1, le=1000)) -> dict[str, Any]:
        items = _safe_file_items(store, limit=limit)
        return {"files": items, "count": len(items)}

    @router.get("/api/files/preview", response_model=FilePreviewResponse)
    def file_preview(path: str) -> dict[str, Any]:
        target = store.runtime.project_root / path
        allowed, reason = store.runtime.safety.file_guard.validate_read(target)
        if not allowed:
            status_code = 404 if "does not exist" in reason.lower() else 403
            raise HTTPException(status_code=status_code, detail="File preview is not available.")
        result = _run_tool(store, "read_file", {"path": path})
        if not result.success:
            raise HTTPException(status_code=403, detail="File preview is not available.")
        content = store.runtime.safety.redact(result.content)
        max_chars = 20_000
        return {"path": path, "content": content[:max_chars], "truncated": len(content) > max_chars}

    @router.get("/api/git/diff", response_model=GitDiffResponse)
    def git_diff() -> dict[str, Any]:
        result = _run_tool(store, "git_diff", {})
        diff = store.runtime.safety.redact(result.content if result.success else "")
        return {"diff": diff, "changed_files": _changed_files(store)}

    @router.post("/api/chat")
    def chat(payload: ChatRequest) -> dict[str, Any]:
        return store.chat(
            payload.message, session_id=payload.session_id, mode=parse_mode(payload.mode)
        )

    @router.get("/api/tasks")
    def list_tasks(project_id: str | None = None) -> dict[str, Any]:
        selected = project_id or store.active_project_id
        if store.app_store.get_project(selected) is None:
            raise HTTPException(status_code=404, detail="Unknown project.")
        return {"project_id": selected, "tasks": store.list_tasks(selected)}

    @router.post("/api/tasks/plan")
    def plan(payload: PlanRequest) -> dict[str, Any]:
        _validate_project_path(payload.project_path, store.runtime.project_root)
        if payload.project_id and store.app_store.get_project(payload.project_id) is None:
            raise HTTPException(status_code=404, detail="Unknown project.")
        task_session = store.create_plan(
            payload.task,
            mode=parse_mode(payload.mode),
            project_id=payload.project_id,
        )
        return serialize_task_session(task_session)

    @router.post("/api/tasks/{task_id}/propose")
    def propose(task_id: str) -> dict[str, Any]:
        try:
            task_session = store.propose(task_id)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return serialize_task_session(task_session)

    @router.post("/api/tasks/{task_id}/propose-fix")
    def propose_fix(task_id: str) -> dict[str, Any]:
        try:
            task_session = store.propose_fix(task_id)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return serialize_task_session(task_session)

    @router.post("/api/tasks/{task_id}/run")
    def run(task_id: str) -> dict[str, Any]:
        try:
            task_session = store.run_task(task_id)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return serialize_task_session(task_session)

    @router.post("/api/tasks/{task_id}/approve")
    def approve(task_id: str, payload: ApprovalRequestModel) -> dict[str, Any]:
        if not store.approve(task_id, step_id=payload.step_id, action=payload.action):
            raise HTTPException(status_code=404, detail="Unknown task or approval.")
        task_session = store.get_task(task_id)
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return serialize_task_session(task_session)

    @router.post("/api/tasks/{task_id}/reject")
    def reject(task_id: str, payload: ApprovalRequestModel) -> dict[str, Any]:
        if not store.reject(task_id, step_id=payload.step_id, action=payload.action):
            raise HTTPException(status_code=404, detail="Unknown task or approval.")
        task_session = store.get_task(task_id)
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return serialize_task_session(task_session)

    @router.post("/api/tasks/{task_id}/repeat")
    def repeat(task_id: str) -> dict[str, Any]:
        task_session = store.repeat_task(task_id)
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return serialize_task_session(task_session)

    @router.post("/api/tasks/{task_id}/continue")
    def continue_task(task_id: str, payload: ContinueTaskRequest) -> dict[str, Any]:
        try:
            task_session = store.continue_task(task_id, payload.message)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return serialize_task_session(task_session)

    @router.post("/api/tasks/{task_id}/rollback")
    def rollback(task_id: str, payload: RollbackRequest) -> dict[str, Any]:
        try:
            task_session = store.rollback(
                task_id, confirm_created_deletions=payload.confirm_created_deletions
            )
        except RollbackConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return serialize_task_session(task_session)

    @router.get("/api/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        task_session = store.get_task(task_id)
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return serialize_task_session(task_session)

    @router.get("/api/tasks/{task_id}/messages")
    def get_messages(task_id: str) -> dict[str, Any]:
        if store.app_store.get_task(task_id) is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return {"task_id": task_id, "messages": store.app_store.list_messages(task_id)}

    @router.get("/api/tasks/{task_id}/events")
    def get_events(task_id: str) -> dict[str, Any]:
        task_session = store.get_task(task_id)
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return {"events": task_session.events}

    @router.get("/api/tasks/{task_id}/timeline", response_model=TimelineResponse)
    def get_timeline(task_id: str) -> dict[str, Any]:
        task_session = store.get_task(task_id)
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        events: list[dict[str, Any]] = [
            {
                "type": "task_status",
                "title": _event_title("task_status"),
                "status": task_session.status,
            }
        ]
        for event in task_session.events:
            event_type = str(event.get("type", "event"))
            events.append(
                {
                    "type": event_type,
                    "title": str(event.get("title") or _event_title(event_type)),
                    "step_id": event.get("step_id"),
                    "action": event.get("action"),
                    "status": event.get("status"),
                }
            )
        return {"task_id": task_id, "events": events}

    @router.get("/api/tasks/{task_id}/report")
    def get_report(task_id: str) -> dict[str, Any]:
        task_session = store.get_task(task_id)
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return {"report": task_session.final_report_text, "report_path": task_session.report_path}

    @router.get("/api/tasks/{task_id}/diff")
    def get_diff(task_id: str) -> dict[str, Any]:
        task_session = store.get_task(task_id)
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return {"diff": task_session.proposed_patch or "", "files": task_session.proposed_files}

    @router.get("/api/settings")
    def get_settings() -> dict[str, Any]:
        return store.settings()

    @router.post("/api/settings")
    def update_settings(payload: SettingsUpdateRequest) -> dict[str, Any]:
        try:
            return store.update_settings(payload.model_dump(exclude_none=True))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/maintenance/cache/clear")
    def clear_cache() -> dict[str, Any]:
        store.clear_cache()
        return {"cleared": True}

    @router.get("/api/logs/export")
    def export_logs() -> Response:
        parts: list[str] = []
        for path in sorted(store.app_store.paths.logs.glob("*.log")):
            parts.append(f"===== {path.name} =====\n")
            parts.append(
                store.runtime.safety.redact(path.read_text(encoding="utf-8", errors="replace"))
            )
        content = "\n".join(parts) if parts else "No application logs have been recorded.\n"
        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": 'attachment; filename="complex-agent-logs.txt"'},
        )

    @router.get("/")
    def index(request: Request):  # type: ignore[no-untyped-def]
        return request.app.state.index_response()

    return router


def _latest_run_summary(store: SessionStore) -> dict[str, Any] | None:
    tasks = store.list_tasks(store.active_project_id)
    if not tasks:
        return None
    latest = tasks[0]
    run = store.app_store.latest_run(str(latest["id"]))
    return {
        "id": latest["id"],
        "mode": latest["mode"],
        "goal": latest["title"],
        "status": latest["status"],
        "created_at": latest["created_at"],
        "summary": run["status"] if run else "",
    }


def _validate_project_path(project_path: str | None, configured_root: Path) -> None:
    if not project_path:
        return
    requested = Path(project_path).expanduser().resolve()
    if requested != configured_root:
        raise HTTPException(
            status_code=400, detail="Use /api/project/select before planning in another folder."
        )


def _project_public(project: dict[str, Any], *, active_id: str) -> dict[str, Any]:
    return {
        "id": project["id"],
        "name": project["name"],
        "root_path": project["root_path"],
        "mount_id": project.get("mount_id"),
        "host_path": project.get("host_path"),
        "container_path": project.get("container_path") or project["root_path"],
        "created_at": project["created_at"],
        "updated_at": project["updated_at"],
        "last_opened_at": project["last_opened_at"],
        "is_archived": bool(project["is_archived"]),
        "default_model": project["default_model"],
        "default_mode": project["default_mode"],
        "last_task_title": project.get("last_task_title"),
        "is_active": project["id"] == active_id,
    }


def _project_response(store: SessionStore) -> dict[str, Any]:
    root = store.runtime.project_root
    project = store.app_store.get_project(store.active_project_id) or {}
    decision = store.project_guard.evaluate(root)
    return {
        "id": store.active_project_id,
        "name": project.get("name", root.name),
        "project_root": str(root),
        "exists": root.exists() and root.is_dir(),
        "writable": root.exists() and root.is_dir() and os.access(root, os.W_OK),
        "warning": decision.warning,
    }


def _tool_context(store: SessionStore) -> ToolContext:
    return ToolContext(project_root=store.runtime.project_root, safety=store.runtime.safety)


def _run_tool(store: SessionStore, name: str, data: dict[str, object]):  # type: ignore[no-untyped-def]
    return store.runtime.registry.run(name, data, _tool_context(store))


def _safe_file_items(store: SessionStore, *, limit: int) -> list[dict[str, str]]:
    result = _run_tool(store, "list_files", {"path": ".", "pattern": "*", "limit": limit})
    if not result.success:
        return []
    items = []
    for line in result.content.splitlines():
        path = line.strip()
        if not path:
            continue
        allowed, _ = store.runtime.safety.file_guard.validate_read(
            store.runtime.project_root / path
        )
        if not allowed:
            continue
        file_path = Path(path)
        items.append(
            {
                "path": path,
                "name": file_path.name,
                "directory": file_path.parent.as_posix()
                if file_path.parent.as_posix() != "."
                else "",
                "extension": file_path.suffix,
            }
        )
    return items


def _important_directories(store: SessionStore) -> list[str]:
    directories = []
    for name in ["src", "tests", "docs", "config", "examples"]:
        path = store.runtime.project_root / name
        allowed, _ = store.runtime.safety.file_guard.validate_read(path)
        if allowed and path.is_dir():
            directories.append(name)
    return directories


def _git_branch(store: SessionStore) -> str | None:
    result = _run_tool(store, "git_branch", {})
    if not result.success:
        return None
    branch = store.runtime.safety.redact(result.content).strip()
    return branch or None


def _changed_files(store: SessionStore) -> list[dict[str, str]]:
    collected: dict[str, str] = {}
    result = _run_tool(store, "git_status", {})
    if not result.success:
        return []
    for line in result.content.splitlines():
        parsed = _parse_git_status_line(line)
        if parsed is None:
            continue
        path, status = parsed
        if _safe_changed_path(store, path):
            collected[path] = status
    return [{"path": path, "status": status} for path, status in sorted(collected.items())]


def _safe_changed_path(store: SessionStore, path: str) -> bool:
    normalized = path.replace("\\", "/").strip()
    if not normalized:
        return False
    if " -> " in normalized:
        normalized = normalized.rsplit(" -> ", 1)[-1]
    allowed, _ = store.runtime.safety.file_guard.validate_write(
        store.runtime.project_root / normalized
    )
    return allowed


def _parse_git_status_line(line: str) -> tuple[str, str] | None:
    if len(line) < 4:
        return None
    code = line[:2]
    path = line[3:].strip()
    if not path:
        return None
    if "A" in code or "??" in code:
        status = "added"
    elif "D" in code:
        status = "deleted"
    else:
        status = "modified"
    return path, status


def _event_title(event_type: str) -> str:
    titles = {
        "task_status": "Состояние задачи",
        "pending_approval": "Ожидается подтверждение",
        "approval_granted": "Действие подтверждено",
        "approval_rejected": "Действие отклонено",
        "task_started": "Задача запущена",
        "task_finished": "Задача завершена",
        "llm_unavailable": "Ollama недоступен",
        "patch_proposed": "Предложены изменения",
        "patch_applied": "Patch применён",
        "patch_failed": "Patch не применён",
        "verification_finished": "Проверка завершена",
        "proposal_failed": "Не удалось предложить изменения",
        "rollback_completed": "Изменения откачены",
        "task_continued": "Задача продолжена",
    }
    return titles.get(event_type, event_type)
