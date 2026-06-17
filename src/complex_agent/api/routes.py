from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from complex_agent.api.schemas import ApprovalRequestModel, ChatRequest, PlanRequest
from complex_agent.api.session_store import (
    SessionStore,
    parse_mode,
    read_report,
    serialize_task_session,
)


def create_router(store: SessionStore) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "local_only": True}

    @router.get("/api/status")
    def status() -> dict[str, Any]:
        return {
            "project_root": str(store.runtime.project_root),
            "mode": "review",
            "tool_count": len(store.runtime.registry.list_tools()),
            "agent_state_exists": (store.runtime.project_root / ".agent").exists(),
            "latest_run": _latest_run_summary(store.runtime.project_root),
        }

    @router.get("/api/tools")
    def tools() -> dict[str, Any]:
        return {"tools": store.runtime.registry.list_tool_info(include_all=True)}

    @router.post("/api/chat")
    def chat(payload: ChatRequest) -> dict[str, Any]:
        return store.chat(payload.message, session_id=payload.session_id, mode=parse_mode(payload.mode))

    @router.post("/api/tasks/plan")
    def plan(payload: PlanRequest) -> dict[str, Any]:
        _validate_project_path(payload.project_path, store.runtime.project_root)
        task_session = store.create_plan(payload.task, mode=parse_mode(payload.mode))
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

    @router.get("/api/tasks/{task_id}/report")
    def get_report(task_id: str) -> dict[str, Any]:
        task_session = store.get_task(task_id)
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
        return {"report": read_report(task_session.report_path), "report_path": task_session.report_path}

    @router.get("/api/tasks/{task_id}/diff")
    def get_diff(task_id: str) -> dict[str, Any]:
        task_session = store.get_task(task_id)
        if task_session is None:
            raise HTTPException(status_code=404, detail="Unknown task.")
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
        raise HTTPException(status_code=400, detail="MVP 2 uses the configured project root only.")

