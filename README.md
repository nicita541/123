# Complex AI Coding Agent

Local, safety-first coding-agent MVP for task-centered development. The agent can plan a
task, propose a Diff, wait for approval, apply an approved patch through `ApplyPatchTool`,
run safe checks, and generate a final report.

## Quick Start

```powershell
cd F:\aiAgent
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m complex_agent.main serve --project . --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

Useful CLI checks:

```powershell
.venv\Scripts\python.exe -m complex_agent.main --project . status
.venv\Scripts\python.exe -m complex_agent.main --project . tools
.venv\Scripts\python.exe -m complex_agent.main --project . plan "Audit this project"
```

## Local Task-Centered Workspace

The browser UI is a dark Russian task-centered workspace:

- left sidebar with project selection and task history;
- centered task feed with plan, Diff, approval, verification, and report cards;
- right floating `Среда` card with project, git, model, and progress status;
- bottom composer for new tasks.

The UI does not expose direct write, shell, raw patch, or arbitrary git endpoints.

## Desktop App

Install desktop extra:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[desktop]"
```

Run:

```powershell
.venv\Scripts\python.exe -m complex_agent.main desktop --project F:\1
```

Desktop mode opens the same local UI in a `pywebview` window titled `Локальный агент`.
It starts a localhost FastAPI backend and stops it when the window closes.

If `pywebview` is not installed, the CLI prints:

```text
Desktop mode requires pywebview. Install with: pip install -e ".[desktop]"
```

## Folder Selection And Sandbox

Use `Выбрать папку` in the sidebar and enter a local directory path manually.

The backend exposes:

```text
GET  /api/project
POST /api/project/select
```

After selecting a folder, the runtime is recreated for that project root. All file
listing, preview, search, patch application, git diff/status, shell checks, artifacts,
and reports are constrained to that selected folder.

Sandbox rule:

```text
The agent can change files only inside the selected project folder.
```

Forbidden paths such as `.env`, `.agent`, `.venv`, `__pycache__`, private keys,
secret folders, and token folders are hidden or blocked.

## Approval Flow

The safe edit flow is:

```text
task -> plan -> proposed Diff -> approval -> ApplyPatchTool -> check -> final report
```

No patch is applied before approval. Rejected changes do not mutate files.

## Calculator Demo

The calculator demo is deterministic and works without Ollama.

Task:

```text
Создай консольный калькулятор на Python
```

Expected result:

- a plan appears;
- a `calculator.py` Diff is proposed;
- `calculator.py` is not created before approval;
- after approval the patch is applied through `ApplyPatchTool`;
- `python calculator.py --self-test` passes;
- a final report is created.

Demo-created `calculator.py` is generated output unless you explicitly decide to keep it.

## Local Ollama Models

Ollama is optional. Deterministic skills keep working when Ollama is unavailable.

Install and pull a coding model:

```powershell
ollama pull qwen3-coder:30b
ollama pull qwen2.5-coder:14b
ollama pull qwen2.5-coder:7b-instruct
set OLLAMA_MODEL=qwen2.5-coder:7b-instruct
```

Optional overrides:

```powershell
set OLLAMA_BASE_URL=http://127.0.0.1:11434
set OLLAMA_MODEL=qwen2.5-coder:7b-instruct
```

If the configured model is missing, the provider selects the best available local model:

1. `qwen3-coder:30b`
2. `qwen2.5-coder:14b`
3. `qwen2.5-coder:7b-instruct`
4. `qwen3:8b`
5. first available model

`status` and `/api/status` show provider, base URL, selected model, reachable status,
generation check status, and the local model list from `/api/tags`.

Ollama may generate structured plans or proposed unified diffs. It never writes files
directly; all patches still pass validation, safety checks, and approval.

## Generic Ollama Demo

Task:

```text
Создай snake.py: простая консольная змейка на Python без внешних зависимостей. Не запускай интерактивную игру, только проверь синтаксис.
```

Expected flow:

- the agent uses Ollama, not the deterministic calculator skill;
- a plan appears;
- a proposed Diff includes `snake.py`;
- `snake.py` does not exist before approval;
- after approval, `ApplyPatchTool` creates `snake.py`;
- `python -m py_compile snake.py` passes;
- the final report explains how to run and verify the file.

## Docker

Docker mode runs the same FastAPI/static UI server in a Python 3.12 container. Mount only
the workspace the agent may change:

```powershell
cd F:\aiAgent
$env:AGENT_WORKSPACE = "F:\1"
$env:OLLAMA_BASE_URL = "http://host.docker.internal:11434"
$env:OLLAMA_MODEL = "qwen3-coder:30b"
docker compose up --build agent-app
```

Open:

```text
http://127.0.0.1:8765
```

The container uses `/workspace` as the selected project root. Do not mount a whole drive
or home directory. See [docs/docker.md](docs/docker.md).

## Validation

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m unittest discover
.venv\Scripts\python.exe -m compileall -q src tests
```

Generated directories such as `.agent/`, `.venv/`, `__pycache__/`, and cache/build
outputs should not be committed.
