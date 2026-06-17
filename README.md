# Complex AI Coding Agent

Complex AI Coding Agent is a modular, safety-first MVP for a coding agent. It can create plans, scan projects, run restricted tools, keep run history, and produce final reports without giving the language model direct access to files or shell commands.

## Quick Start

```powershell
python -m pip install -e .[dev]
agent plan "Audit this project"
agent audit --project .
python -m pytest
```

The package also works in a minimal environment without Typer/Pydantic installed:

```powershell
$env:PYTHONPATH="src"
python -m complex_agent.main plan "Audit this project"
python -m unittest discover
```

## Modes

- `chat`: no file reads and no commands.
- `plan`: read-only project inspection and planning.
- `review`: default mode; proposes changes and requires approval before mutation.
- `dev`: approved writes and verification commands.
- `auto`: bounded autonomous loop with strict limits.
- `audit`: read-only project audit report.

## Safety Defaults

- Sensitive files such as `.env`, private keys, credentials and token files are denied.
- Dangerous commands such as `git reset --hard`, `git clean`, `git push`, recursive delete and credential commands are blocked.
- Mutating tools require approval outside explicit development flows.
- Tool outputs are redacted before they are logged or sent into context.

## Local Agent App

MVP 2 adds a local FastAPI app with a Russian static chat UI. It is local-only by default and does not include production authentication or a frontend build pipeline.

Run from `F:\aiAgent`:

```powershell
.venv\Scripts\python.exe -m complex_agent.main serve --project . --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

Minimal workflow:

1. Enter a task in the chat or use `Создать план`.
2. Review the plan shown in the right panel.
3. Press `Выполнить план`.
4. Approve or reject pending actions if required.
5. Inspect `События`, `Проверки`, `Diff/Различия`, changed files, and `Отчёт`.

See `docs/mvp2_local_agent_app.md` for endpoint details and MVP 2 limits.

## Codex-like Local Workspace

MVP 3 keeps the same local-only backend but presents it as a Russian coding-agent workspace: `Рабочая область`, `Чат + задача`, `План / действия`, and bottom `Workbench`.

Run from `F:\aiAgent`:

```powershell
.venv\Scripts\python.exe -m complex_agent.main serve --project . --host 127.0.0.1 --port 8765
```

Workflow:

1. Open `http://127.0.0.1:8765`.
2. Browse safe project files in `Рабочая область`.
3. Enter a task in `Чат + задача`.
4. Use `Составить план`, then review the right-side plan.
5. Use `Выполнить` and handle `Подтверждение` cards when required.
6. Inspect `Diff`, `Терминал`, `Проверки`, `Журнал`, and `Отчёт`.

See `docs/mvp3_codex_like_workspace.md` for added endpoints and MVP 3 safety limits.

## Final Local Coding Agent MVP

The final MVP keeps the local FastAPI/static UI shape and adds an end-to-end safe edit flow:

```text
task -> plan -> proposed diff -> approval -> ApplyPatchTool -> self-test -> final report
```

The calculator demo is deterministic and works without an LLM. For a task such as
`Сделай консольный калькулятор на Python`, the agent proposes a `calculator.py` diff,
waits for approval, applies the patch through `ApplyPatchTool`, runs
`python calculator.py --self-test`, and stores a final report.

Unknown tasks may use a local Ollama model to generate a structured plan or proposed
unified diff. Ollama never writes files directly: every patch is validated by the
patch generator, file/secrets safety checks, and the approval flow before
`ApplyPatchTool` can apply it.

See `docs/final_local_coding_agent_mvp.md` for the full workflow and limits.

## Local Ollama Models

Ollama is optional. If it is unavailable, deterministic skills keep working and unknown
LLM-backed tasks return a clear fallback message instead of mutating the project.

Install and pull a local coding model:

```powershell
ollama pull qwen2.5-coder:7b
set OLLAMA_MODEL=qwen2.5-coder:7b
```

Optional overrides:

```powershell
set OLLAMA_BASE_URL=http://127.0.0.1:11434
set OLLAMA_MODEL=qwen2.5-coder:7b
```

Run the agent:

```powershell
.venv\Scripts\python.exe -m complex_agent.main serve --project . --host 127.0.0.1 --port 8765
.venv\Scripts\python.exe -m complex_agent.main --project . status
```

`status` and `/api/status` show provider, model, base URL, and whether Ollama is reachable.

## Development

```powershell
python -m unittest discover
python -m pytest
ruff check .
mypy src
```

## Phase 1 baseline validation

Phase 1 stable baseline is documented in `docs/phase1_baseline.md`.

Run from `F:\aiAgent`:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m unittest discover
.venv\Scripts\python.exe -m compileall -q src tests
```

Current baseline expectation: all three commands pass. Generated directories such as `.agent/`, `.venv/`, `__pycache__/`, and cache/build outputs should not be committed.
