# Product Readiness Audit

## Current baseline

The repository is a functional local coding-agent demo, but it is not yet suitable for
continuous daily use. The safe plan, proposed diff, approval, patch, verification, and
report flow exists, together with a FastAPI application, static web UI, pywebview desktop
launcher, Docker files, Ollama integration, and automated tests.

Baseline recorded on 2026-06-18:

- `pytest` passes 81 tests and 55 subtests when Ollama is pointed at a fast failing local
  endpoint. With the normal configuration the suite can wait for the 60 second generation
  probe performed by `/api/status`.
- `unittest discover` passes 77 tests when the same network probe is disabled.
- `compileall` passes.
- Ruff reports three fixable findings.
- mypy reports 25 errors across 18 files.
- `docker compose config` succeeds, but its default bind source
  `examples/demo_project` does not exist.

## 1. What already works

- Ollama-first structured plan generation and unified-diff proposal generation.
- Deterministic fallback is gated by `AGENT_ENABLE_DEMO_FALLBACK` and is disabled by
  default.
- Project-root constrained file, patch, search, git, and shell tools.
- Explicit approval before proposed patches are applied.
- FastAPI and a Russian static web UI for plan, diff, approval, verification, and report.
- A pywebview desktop launcher that serves the same local application.
- A non-root Docker image and compose configuration.
- Focused API, UI, safety, Ollama, desktop, Docker, and tool tests.

## 2. Daily-use blockers

- `SessionStore` keeps chats and task sessions in process memory. A restart loses web task
  history, plans, diffs, approvals, verification logs, and reports.
- Selecting a different directory recreates the runtime and clears all in-memory sessions.
- Existing SQLite run history and artifacts live under each project's `.agent` directory,
  which pollutes workspaces and does not provide a global project manager.
- The UI renders only the current in-memory task and synthesizes history entries in the
  browser. Projects cannot be searched, archived, or restored after restart.
- The task state vocabulary differs between the core, API, and UI and has no persistent
  transition enforcement.
- Verification failure is terminal; it cannot generate an Ollama fix proposal and re-enter
  approval.
- Rollback is a stub and no pre-apply snapshots are captured.
- `ShellTool` uses `command.split()`, so quoted arguments and exact command-policy matching
  are unreliable.
- Project selection accepts drive roots, a whole user home, and system directories.
- CLI execution and web execution use different orchestration and persistence paths.
- `/api/status` performs a live Ollama generation call, making a read-only status request
  slow and causing offline test runs to hang.
- The desktop scripts are hard-coded to local paths; no dependency installer script exists.

## 3. Placeholders and inactive boundaries

- `src/complex_agent/api/auth.py`: local-only disabled auth marker.
- `src/complex_agent/tools/mcp/adapter.py`: MCP placeholder, not registered.
- `src/complex_agent/subagents/base.py`: subagent placeholder, not integrated.
- `src/complex_agent/memory/long_term_memory.py` and `vector_memory.py`: future memory
  boundaries, not part of the application workflow.
- `src/complex_agent/execution/rollback_manager.py`: non-functional rollback stub.
- `src/complex_agent/tools/web/*`: disabled web-tool placeholders.
- `src/complex_agent/llm/openai_provider.py`: non-functional provider placeholder; Ollama is
  the only active model provider.
- `src/complex_agent/tools/code/symbol_index_tool.py`: inactive future AST/LSP placeholder.
- `src/complex_agent/planning/planner.py`: deterministic CLI planner remains separate from
  the Ollama plan/diff application workflow.
- `src/complex_agent/api/routes.py`: `_event_title` is defined twice.

These modules must remain unregistered and explicitly documented as future boundaries, or
be removed when they no longer define a useful interface. They must not appear as working
product features.

## 4. Productization work required now

1. Move projects, tasks, messages, plans, proposals, approvals, runs, settings, reports,
   and rollback metadata into a global SQLite application store.
2. Bind every task operation to its persisted project rather than the currently selected
   UI project.
3. Introduce one persistent task state machine and support fix proposals after failed
   verification.
4. Capture pre-apply snapshots and provide conflict-aware, confirmed rollback through a
   guarded mutating tool.
5. Replace string splitting with an argv-only shell contract and add broad-root rejection.
6. Build real project and task-history surfaces in the UI, including settings and restored
   task feeds.
7. Make browser, desktop, CLI, and Docker use the same application storage and workflow.
8. Remove misleading placeholder controls and resolve Ruff/mypy failures.
9. Add persistence, multi-project, rollback, state-transition, and packaging coverage.
10. Record automated and manual validation honestly in the final productization report.

## Security constraints retained

- Project mutations remain limited to the selected task's project root.
- Reads and writes continue through `FileGuard`; shell continues through `CommandGuard`.
- No raw write, raw patch, raw shell, or arbitrary git API is added.
- No automatic commit, push, destructive cleanup, or cloud authentication is added.
- Application storage is internal state and is not exposed as a selectable coding project.
