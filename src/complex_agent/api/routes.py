from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from complex_agent.api.schemas import (
    ApprovalRequestModel,
    ChatRequest,
    FileListResponse,
    FilePreviewResponse,
    GitDiffResponse,
    PlanRequest,
    ProjectResponse,
    ProjectSelectRequest,
    TimelineResponse,
    WorkspaceResponse,
)
from complex_agent.api.session_store import (
    SessionStore,
    parse_mode,
    read_report,
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
        llm_status = store.patch_generator.llm_status()
        return {
            "project_root": str(store.runtime.project_root),
            "mode": "review",
            "tool_count": len(store.runtime.registry.list_tools()),
            "agent_state_exists": (store.runtime.project_root / ".agent").exists(),
            "latest_run": _latest_run_summary(store.runtime.project_root),
            "llm_provider": llm_status["llm_provider"],
            "ollama_base_url": llm_status["ollama_base_url"],
            "ollama_model": llm_status["ollama_model"],
            "ollama_reachable": llm_status["ollama_reachable"],
            "ollama_generation_check": llm_status.get("ollama_generation_check", False),
            "ollama_models": llm_status.get("ollama_models", []),
            "fallback_provider": llm_status.get("fallback_provider", "deterministic"),
        }

    @router.get("/api/tools")
    def tools() -> dict[str, Any]:
        return {"tools": store.runtime.registry.list_tool_info(include_all=True)}

    @router.get("/api/project", response_model=ProjectResponse)
    def get_project() -> dict[str, Any]:
        return _project_response(store)

    @router.post("/api/project/select", response_model=ProjectResponse)
    def select_project(payload: ProjectSelectRequest) -> dict[str, Any]:
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
        truncated = len(content) > max_chars
        return {"path": path, "content": content[:max_chars], "truncated": truncated}

    @router.get("/api/git/diff", response_model=GitDiffResponse)
    def git_diff() -> dict[str, Any]:
        result = _run_tool(store, "git_diff", {})
        diff = store.runtime.safety.redact(result.content if result.success else "")
        return {"diff": diff, "changed_files": _changed_files(store)}

    @router.post("/api/chat")
    def chat(payload: ChatRequest) -> dict[str, Any]:
        return store.chat(payload.message, session_id=payload.session_id, mode=parse_mode(payload.mode))

    @router.post("/api/tasks/plan")
    def plan(payload: PlanRequest) -> dict[str, Any]:
        _validate_project_path(payload.project_path, store.runtime.project_root)
        task_session = store.create_plan(payload.task, mode=parse_mode(payload.mode))
        return serialize_task_session(task_session)

    @router.post("/api/tasks/{task_id}/propose")
    def propose(task_id: str) -> dict[str, Any]:
        task_session = store.propose(task_id)
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return serialize_task_session(task_session)

    @router.post("/api/tasks/{task_id}/run")
    def run(task_id: str) -> dict[str, Any]:
        task_session = store.run_task(task_id)
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

    @router.get("/api/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        task_session = store.get_task(task_id)
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        task_session.pending_approvals = store.collect_pending_approvals(task_session)
        return serialize_task_session(task_session)

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
        events = []
        if task_session.status:
            events.append(
                {
                    "type": "task_status",
                    "title": _event_title("task_status"),
                    "status": task_session.status,
                }
            )
        for event in task_session.events:
            event_type = str(event.get("type", "event"))
            events.append(
                {
                    "type": event_type,
                    "title": _event_title(event_type),
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
        if task_session.final_report_text:
            return {"report": task_session.final_report_text, "report_path": task_session.report_path}
        return {"report": read_report(task_session.report_path), "report_path": task_session.report_path}

    @router.get("/api/tasks/{task_id}/diff")
    def get_diff(task_id: str) -> dict[str, Any]:
        task_session = store.get_task(task_id)
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        if task_session.proposed_patch:
            return {"diff": task_session.proposed_patch}
        diff = ""
        if task_session.state:
            for observation in task_session.state.observations:
                if observation.source == "git_diff":
                    diff = observation.content
                    break
        return {"diff": diff}

    @router.get("/")
    def index(request: Request):  # type: ignore[no-untyped-def]
        return request.app.state.index_response()

    return router


def _latest_run_summary(project_root: Path) -> dict[str, Any] | None:
    db_path = project_root / ".agent" / "runs.sqlite3"
    if not db_path.exists():
        return None
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, mode, status, goal, summary FROM runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return {
        "id": row[0],
        "mode": row[1],
        "status": row[2],
        "goal": row[3],
        "summary": row[4],
    }


def _validate_project_path(project_path: str | None, configured_root: Path) -> None:
    if not project_path:
        return
    requested = Path(project_path).expanduser().resolve()
    if requested != configured_root:
        raise HTTPException(status_code=400, detail="Use /api/project/select before planning in another folder.")


def _project_response(store: SessionStore) -> dict[str, Any]:
    root = store.runtime.project_root
    return {
        "project_root": str(root),
        "exists": root.exists() and root.is_dir(),
        "writable": root.exists() and root.is_dir() and os.access(root, os.W_OK),
    }


def _tool_context(store: SessionStore) -> ToolContext:
    return ToolContext(project_root=store.runtime.project_root, safety=store.runtime.safety)


def _run_tool(store: SessionStore, name: str, data: dict[str, object]):
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
        allowed, _ = store.runtime.safety.file_guard.validate_read(store.runtime.project_root / path)
        if not allowed:
            continue
        file_path = Path(path)
        items.append(
            {
                "path": path,
                "name": file_path.name,
                "directory": file_path.parent.as_posix() if file_path.parent.as_posix() != "." else "",
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
    for task_session in store.task_sessions.values():
        if not task_session.state:
            continue
        for path in task_session.state.changed_files:
            if _safe_changed_path(store, path):
                collected[path] = "modified"
    if collected:
        return [{"path": path, "status": status} for path, status in sorted(collected.items())]

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
    allowed, _ = store.runtime.safety.file_guard.validate_write(store.runtime.project_root / normalized)
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
        "step_started": "Шаг запущен",
        "step_finished": "Шаг завершён",
        "tool_called": "Инструмент вызван",
        "tool_finished": "Инструмент завершён",
        "llm_unavailable": "Ollama недоступен",
        "patch_proposed": "Предложены изменения",
        "patch_applied": "Patch применён",
        "patch_failed": "Patch не применён",
        "verification_finished": "Проверка завершена",
        "proposal_failed": "Не удалось предложить изменения",
    }
    return titles.get(event_type, event_type)


def _event_title(event_type: str) -> str:  # type: ignore[no-redef]
    titles = {
        "task_status": "Состояние задачи",
        "pending_approval": "Ожидается подтверждение",
        "approval_granted": "Действие подтверждено",
        "approval_rejected": "Действие отклонено",
        "task_started": "Задача запущена",
        "task_finished": "Задача завершена",
        "step_started": "Шаг запущен",
        "step_finished": "Шаг завершён",
        "tool_called": "Инструмент вызван",
        "tool_finished": "Инструмент завершён",
        "llm_unavailable": "Ollama недоступен",
        "patch_proposed": "Предложены изменения",
        "patch_applied": "Patch применён",
        "patch_failed": "Patch не применён",
        "verification_finished": "Проверка завершена",
        "proposal_failed": "Не удалось предложить изменения",
    }
    return titles.get(event_type, event_type)
