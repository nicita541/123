from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from complex_agent.api.session_store import SessionStore, TaskSession, serialize_task_session
from complex_agent.app import AgentRuntime
from complex_agent.core.modes import AgentMode
from complex_agent.storage.app_store import AppStore
from complex_agent.ui.console_renderer import ConsoleRenderer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent", description="Complex AI Coding Agent MVP")
    parser.add_argument("--project", default=".", help="Project root path.")
    parser.add_argument("--yes", action="store_true", help="Auto-approve approval-gated actions.")
    parser.add_argument("--app-data", default=None, help="Override global application data directory.")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ["plan", "review", "run"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("task")
    sub.add_parser("audit").add_argument("task", nargs="?", default="Audit this project")
    sub.add_parser("tools")
    sub.add_parser("status")
    sub.add_parser("history")
    sub.add_parser("config")
    serve = sub.add_parser("serve")
    serve.add_argument("--project", dest="serve_project", default=None, help="Project root path.")
    serve.add_argument("--host", default="127.0.0.1", help="Host to bind. Defaults to localhost.")
    serve.add_argument("--port", default=8765, type=int, help="Port to bind.")
    return parser


def create_serve_app(project_path: str | Path, host: str) -> Any:
    from complex_agent.api.server import create_app

    return create_app(project_path=project_path, host=host)


def run_serve(project_path: str | Path, *, host: str, port: int) -> int:
    import uvicorn

    app = create_serve_app(project_path, host)
    print(f"Local Agent App: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "serve":
        project = Path(args.serve_project or args.project)
        return run_serve(project, host=args.host, port=args.port)
    try:
        app_store = AppStore(args.app_data)
        runtime = AgentRuntime(
            project_path=Path(args.project),
            auto_approve=False,
            app_data_path=app_store.paths.root,
        )
        service = SessionStore(runtime, app_store)
    except ValueError as exc:
        print(str(exc))
        return 2
    renderer = ConsoleRenderer()

    if args.command == "plan":
        session = service.create_plan(args.task, mode=AgentMode.PLAN)
        print(renderer.render_plan(session.plan))
        return 0 if session.status != "failed" else 1
    if args.command == "review":
        session = service.create_plan(args.task, mode=AgentMode.REVIEW)
        print(renderer.render_plan(session.plan))
        if session.status == "failed":
            return 1
        proposed = service.propose(session.id)
        if proposed is None:
            return 1
        _print_proposal(proposed)
        return 0
    if args.command == "run":
        session = service.create_plan(args.task, mode=AgentMode.DEV)
        print(renderer.render_plan(session.plan))
        if session.status == "failed":
            return 1
        proposed = service.propose(session.id)
        if proposed is None:
            return 1
        _print_proposal(proposed)
        approval = proposed.pending_approvals[0] if proposed.pending_approvals else None
        if approval:
            approved = bool(args.yes)
            if not approved and sys.stdin.isatty():
                approved = input("Apply this diff? [y/N] ").strip().lower() in {"y", "yes"}
            if not approved:
                print("Waiting for explicit approval. No files were changed.")
                return 2
            service.approve(
                proposed.id,
                step_id=str(approval["step_id"]),
                action=str(approval["action"]),
            )
        completed = service.run_task(proposed.id)
        if completed is None:
            return 1
        print(completed.final_report_text)
        return 0 if completed.status == "completed" else 1
    if args.command == "audit":
        session = service.create_plan(args.task, mode=AgentMode.AUDIT)
        print(renderer.render_plan(session.plan))
        return 0 if session.status != "failed" else 1
    if args.command == "tools":
        for tool in runtime.registry.list_tool_info(include_all=True):
            print(f"{tool['status']}\t{tool['name']}\t{tool['description']}")
        return 0
    if args.command == "status":
        llm_status = service.status_snapshot()
        print(f"project: {runtime.project_root}")
        print(f"tools: {len(runtime.registry.list_tools())}")
        print(f"LLM provider: {llm_status['llm_provider']}")
        print(f"Ollama base URL: {llm_status['ollama_base_url']}")
        print(f"Ollama model: {llm_status['ollama_model']}")
        print(f"Ollama reachable: {'yes' if llm_status['ollama_reachable'] else 'no'}")
        print(f"Ollama generation check: {'yes' if llm_status['ollama_generation_check'] else 'no'}")
        raw_models = llm_status.get("ollama_models", [])
        models = raw_models if isinstance(raw_models, list) else []
        print("Ollama models: " + (", ".join(str(model) for model in models) if models else "none"))
        return 0
    if args.command == "history":
        for row in service.list_tasks():
            print(f"{row['id']} | {row['mode']} | {row['status']} | {row['title']}")
        return 0
    if args.command == "config":
        for key, value in service.settings().items():
            print(f"{key}: {value}")
        return 0
    parser.print_help()
    return 1


def _print_proposal(session: TaskSession) -> None:
    data = serialize_task_session(session)
    print("\nProposed diff (not applied):\n")
    print(data["proposed_diff"])
    print("Status: waiting for approval")
