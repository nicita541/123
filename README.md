# Complex AI Coding Agent

Complex AI Coding Agent is a local, safety-first MVP for coding tasks. It can inspect a
project, create a plan, propose a diff, wait for approval, apply an approved patch,
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

The browser UI is a dark, Russian task-centered workspace:

- left sidebar with project selection and task history;
- centered task feed with plan, diff, approval, verification, and report cards;
- right floating `Среда` card with project, git, model, and progress status;
- bottom composer for new tasks.

The UI does not expose direct write, shell, raw patch, or arbitrary git endpoints.

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
task -> plan -> proposed diff -> approval -> ApplyPatchTool -> self-test/check -> final report
```

No patch is applied before approval. Rejected changes do not mutate files.

## Calculator Demo

The calculator demo is deterministic and works without Ollama.

Task:

```text
Сделай консольный калькулятор на Python
```

Expected result:

- a plan appears;
- a `calculator.py` diff is proposed;
- `calculator.py` is not created before approval;
- after approval the patch is applied through `ApplyPatchTool`;
- `python calculator.py --self-test` passes;
- a final report is created.

Demo-created `calculator.py` is generated output unless you explicitly decide to keep it.

## Local Ollama Models

Ollama is optional. Deterministic skills keep working when Ollama is unavailable.

Install and pull a coding model:

```powershell
ollama pull qwen2.5-coder:7b
set OLLAMA_MODEL=qwen2.5-coder:7b
```

Optional overrides:

```powershell
set OLLAMA_BASE_URL=http://127.0.0.1:11434
set OLLAMA_MODEL=qwen2.5-coder:7b
```

`status` and `/api/status` show:

- provider;
- base URL;
- selected model;
- reachable status;
- available local models from `/api/tags` when Ollama responds.

Ollama may generate structured plans or proposed unified diffs. It never writes files
directly; all patches still pass validation, safety checks, and approval.

## Validation

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m unittest discover
.venv\Scripts\python.exe -m compileall -q src tests
```

Generated directories such as `.agent/`, `.venv/`, `__pycache__/`, and cache/build
outputs should not be committed.
