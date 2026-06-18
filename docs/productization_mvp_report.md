# Productization MVP Report

## Delivered

- Added a global application data resolver and migration-backed SQLite `AppStore`.
- Persisted projects, tasks, messages, plans, proposals, approvals, runs, events, reports,
  snapshots, settings, local ownership, and visibility metadata.
- Replaced web in-memory history with restart-safe task hydration.
- Added saved/recent/searchable projects, archive/open actions, grouped task history, restored
  task feeds, settings, repeat, continue, fix proposal, and rollback UI flows.
- Bound all task mutations to the task's persisted project ID.
- Added the full product task lifecycle and a maximum-three-iteration fix loop by default.
- Split fast read-only status from the explicit five-second Ollama generation probe.
- Moved normal reports and rollback artifacts outside project directories.
- Added pre-apply snapshots, post-apply hashes, confirmation for deleting created files, and
  conflict-aware rollback through a high-risk `BaseTool`.
- Replaced `command.split()` with argv execution, token-based command policy, `shell=False`,
  and project-root cwd.
- Added drive/home/system project-root rejection to application entry points and the Docker
  wrapper.
- Removed the inactive git commit tool from the product registry and removed placeholder UI
  controls.
- Parameterized desktop scripts, added desktop dependency installation and a pywebview native
  folder bridge.
- Added a persistent Docker `/data` volume and a safe default workspace.

## Storage and projects

Windows stores application data in `%LOCALAPPDATA%\ComplexAgent`; other platforms use
`~\.complex_agent`. `COMPLEX_AGENT_DATA_DIR` overrides this location. The selected coding
project receives no new application database, reports, or snapshot files.

Projects are deduplicated by normalized root path and ordered by last use. Each task stores
its project ID, so changing the active UI project cannot redirect a prior task's file, shell,
patch, verification, or rollback operations.

## Rollback

Every proposed patch is dry-run parsed before approval. Immediately before apply, existing
target bytes and hashes are captured in global artifacts. After apply, the final hashes are
recorded. Rollback restores only when current hashes still match; created files require an
explicit deletion confirmation. Successful and denied rollback attempts remain visible in
task state/events.

## Desktop and Docker

Desktop uses the same FastAPI application, AppStore, project list, and history as browser
mode. pywebview is installed in the validation environment, the command/bridge and friendly
missing-dependency behavior are covered by tests. An interactive GUI window was not opened
during non-interactive validation.

Docker image build and container smoke passed. The container ran as a non-root user,
`/health` returned `ok`, `/api/status` reported `/workspace`, and application data mounted at
`/data`. The container was stopped without deleting the named data volume.

## Validation results

Executed successfully on 2026-06-18:

```text
pytest: 93 passed, 55 subtests passed
unittest discover: 89 passed
compileall: passed
ruff check: passed
mypy src: passed (150 files)
CLI status: passed
CLI tools: passed
docker compose config: passed
Docker build/up health/status smoke: passed
```

Additional smoke results:

- Restart persistence restored calculator task history, diff, verification, and report.
- Two temporary projects retained isolated task lists.
- Rollback denied unconfirmed created-file deletion, succeeded after confirmation, and
  rejected a file modified externally after apply.
- Failed Python verification produced an Ollama-style fix proposal, required a second
  approval, and completed after the corrected patch.
- Host Ollama was reachable; generation check passed with `qwen3-coder:30b` and four local
  models were detected.
- A real Ollama task generated `todo.py` in a temporary project, waited for approval,
  applied the diff, and passed `python -m py_compile todo.py`.

The only test warning is Starlette's deprecation notice for the current `httpx` TestClient
compatibility layer; it does not affect runtime behavior.

## Remaining limitations

- This remains a localhost, single-user product. Team role columns are not authorization.
- Existing project-local `.agent` history is retained but not automatically imported.
- The compact patch engine supports text-file create/modify flows; intentional source-file
  deletion remains outside this MVP.
- Rollback refuses conflicts rather than merging subsequent manual edits.
- Settings do not move an existing live app-data directory; location is selected by env at
  process start and displayed read-only.
- Desktop packaging into a standalone installer is not included.
- MCP, subagents, web tools, OpenAI provider, and long-term/vector memory remain disabled
  future boundaries and are not advertised as working product features.
