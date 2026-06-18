# Complex AI Coding Agent

Local, Ollama-first coding agent for persistent work across multiple projects. It creates a
plan, proposes a unified diff, waits for explicit approval, applies the patch inside the
task's project sandbox, verifies the result, and stores the complete history locally.

## Quick start

```powershell
cd F:\aiAgent
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m complex_agent.main serve --project . --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. Projects, tasks, plans, diffs, approvals, reports, settings,
and rollback metadata survive backend and desktop restarts.

Application data is stored in `%LOCALAPPDATA%\ComplexAgent` on Windows and
`~\.complex_agent` otherwise. Override it for tests or containers with
`COMPLEX_AGENT_DATA_DIR`.

## Safety model

- Every task is permanently bound to a saved project root.
- Drive roots, the complete user home, and system directories cannot be selected.
- File reads and writes pass through `FileGuard`; commands pass through `CommandGuard`.
- Shell execution uses an argv list, `shell=False`, and the task project as cwd.
- Diff approval is required before every patch and every generated fix.
- No raw shell/write/patch/git endpoints, automatic commit, or push exist.
- Rollback checks post-apply hashes and refuses to overwrite later manual edits.

## Ollama

Normal plan and diff generation use Ollama. Configure the URL/model in Settings or with:

```powershell
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL = "qwen2.5-coder:7b-instruct"
```

The deterministic calculator flow is test/demo-only and is disabled unless
`AGENT_ENABLE_DEMO_FALLBACK=true` is explicitly set.

## Desktop

```powershell
scripts\install_desktop_deps.ps1
scripts\run_desktop.ps1 -Project F:\1
```

Desktop mode uses pywebview, the same FastAPI application and the same persistent app data.
Its folder button opens a native directory chooser.

## Docker

```powershell
scripts\docker_run.ps1 -Workspace F:\1
```

Compose mounts only the selected workspace at `/workspace` and keeps application state in
the `agent-data` volume at `/data`. See [docs/docker.md](docs/docker.md).

## Validation

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m unittest discover
.venv\Scripts\python.exe -m compileall -q src tests
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src
.venv\Scripts\python.exe -m complex_agent.main --project . status
.venv\Scripts\python.exe -m complex_agent.main --project . tools
docker compose config
```

Generated `.agent`, virtual environments, caches, and Docker workspace contents remain
ignored. New application history is not written into project directories.
