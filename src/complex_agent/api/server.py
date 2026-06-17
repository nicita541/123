from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from complex_agent.api.routes import create_router
from complex_agent.api.session_store import SessionStore
from complex_agent.app import AgentRuntime


def create_app(project_path: str | Path = ".", host: str = "127.0.0.1") -> FastAPI:
    project_root = Path(project_path).expanduser().resolve()
    runtime = AgentRuntime(project_path=project_root)
    store = SessionStore(runtime)
    web_root = Path(__file__).resolve().parents[1] / "web"

    app = FastAPI(title="Complex AI Coding Agent Local App", version="0.2.0")
    app.state.session_store = store
    app.state.project_root = project_root
    app.state.web_root = web_root
    app.state.index_response = lambda: FileResponse(web_root / "index.html")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_local_origins(host),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    if web_root.exists():
        app.mount("/static", StaticFiles(directory=web_root), name="static")
    app.include_router(create_router(store))
    return app


def _local_origins(host: str) -> list[str]:
    return [
        "http://127.0.0.1:8765",
        "http://localhost:8765",
        f"http://{host}:8765",
    ]

