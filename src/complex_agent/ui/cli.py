from __future__ import annotations

import argparse
from pathlib import Path

from complex_agent.app import AgentRuntime
from complex_agent.codegen.patch_generator import PatchGenerator
from complex_agent.core.modes import AgentMode
from complex_agent.ui.console_renderer import ConsoleRenderer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent", description="Complex AI Coding Agent MVP")
    parser.add_argument("--project", default=".", help="Project root path.")
    parser.add_argument("--yes", action="store_true", help="Auto-approve approval-gated actions.")
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


def create_serve_app(project_path: str | Path, host: str):
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
    runtime = AgentRuntime(project_path=Path(args.project), auto_approve=bool(args.yes))
    renderer = ConsoleRenderer()

    if args.command == "plan":
        _, plan = runtime.plan(args.task, mode=AgentMode.PLAN)
        print(renderer.render_plan(plan))
        return 0
    if args.command == "review":
        state = runtime.run(args.task, mode=AgentMode.REVIEW)
        print(renderer.render_state(state))
        return 0 if state.final_result and state.final_result.success else 1
    if args.command == "run":
        state = runtime.run(args.task, mode=AgentMode.DEV)
        print(renderer.render_state(state))
        return 0 if state.final_result and state.final_result.success else 1
    if args.command == "audit":
        state = runtime.run(args.task, mode=AgentMode.AUDIT)
        print(renderer.render_state(state))
        return 0 if state.final_result and state.final_result.success else 1
    if args.command == "tools":
        for tool in runtime.registry.list_tool_info(include_all=True):
            print(f"{tool['status']}\t{tool['name']}\t{tool['description']}")
        return 0
    if args.command == "status":
        llm_status = PatchGenerator(runtime.safety).llm_status()
        print(f"project: {runtime.project_root}")
        print(f"tools: {len(runtime.registry.list_tools())}")
        print(f"LLM provider: {llm_status['llm_provider']}")
        print(f"Ollama base URL: {llm_status['ollama_base_url']}")
        print(f"Ollama model: {llm_status['ollama_model']}")
        print(f"Ollama reachable: {'yes' if llm_status['ollama_reachable'] else 'no'}")
        return 0
    if args.command == "history":
        for row in runtime.run_store.list_runs():
            print(" | ".join(str(item) for item in row))
        return 0
    if args.command == "config":
        print("Config files live in config/*.yaml. Runtime uses safe built-in defaults in MVP.")
        return 0
    parser.print_help()
    return 1
