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
