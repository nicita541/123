# Full System Analysis

Date: 2026-06-18  
Project root inspected: `F:\aiAgent`

## Executive summary

`complex-ai-agent` is a local Python coding-agent MVP. It currently provides a CLI,
FastAPI backend, static Russian web UI, desktop launcher, safe tool registry, approval
gate, Ollama provider, patch generation, patch application, shell verification, artifact
storage, and tests.

The application is no longer only a CLI skeleton: the browser/desktop UI can create a
task, ask for a plan, propose a Diff, wait for approval, apply the patch through
`ApplyPatchTool`, run a safe check through `ShellTool`, and create a final report.

The main remaining architectural gap before calling it a safe full MVP is routing:
`PatchGenerator` still contains deterministic calculator skill routing. The deterministic
skill is useful as a test/demo fixture, but it must not be the default path when Ollama is
reachable. Final routing should be:

```text
Task -> Ollama plan -> Ollama proposed diff -> validation -> UI Diff
     -> approval -> ApplyPatchTool -> safe verification -> report
```

If Ollama is unavailable, normal coding tasks should fail clearly without creating a fake
plan, fake patch, or file changes. Deterministic fallback should be explicit demo/test-only
behavior.

## 1. General architecture

The project is a safety-first local coding agent written in Python 3.12. It can run as:

- CLI: `python -m complex_agent.main ...`
- local browser server: `python -m complex_agent.main serve --project . --host 127.0.0.1 --port 8765`
- local desktop app: `python -m complex_agent.main desktop --project F:\1`

Primary layers:

- `ui/cli.py`: command-line entrypoint and server/desktop commands.
- `api/server.py` and `api/routes.py`: FastAPI app and HTTP route layer.
- `web/`: static HTML/CSS/JS task-centered UI.
- `desktop/app.py`: starts FastAPI locally and opens the same UI via `pywebview`.
- `api/session_store.py`: in-memory chat/task sessions, project selection, plan/propose/run state.
- `app.py`: `AgentRuntime`, shared runtime wiring for registry, safety, verifier, storage, events.
- `planning/`: generic MVP planner models and validators.
- `codegen/`: patch proposal logic; currently contains Ollama and deterministic routing.
- `llm/`: provider abstraction and `OllamaProvider`.
- `tools/`: safe tools for filesystem, shell, git, code, project, and report.
- `safety/`: `FileGuard`, `CommandGuard`, `SecretsGuard`, `ApprovalGate`, `SafetyPolicy`.
- `storage/`: SQLite run history and artifact files, lazily initialized.
- `verification/` and `review/`: state verification and final report building.
- `tests/`: unit/API/static tests.

LLM access is constrained to provider code. Ollama can generate structured plans or proposed
patches, but it never writes files directly. File writes are only through the registry tool
`apply_patch` after validation and approval.

## 2. Directory structure

### `src/complex_agent/api/`

Purpose: FastAPI server, schemas, routes, and in-memory sessions.

Main files:

- `server.py`: creates FastAPI app, mounts static UI, wires `AgentRuntime` and `SessionStore`.
- `routes.py`: HTTP endpoints for health, status, project selection, workspace, files, git diff, task flow, reports.
- `schemas.py`: Pydantic response/request models for project, workspace, files, approvals, timeline.
- `session_store.py`: core web-flow state machine for chat/task sessions, plan/propose/approve/reject/run.
- `auth.py`: currently a placeholder.

Working behavior:

- read-only endpoints avoid creating `.agent`;
- project selection recreates runtime for selected root;
- proposed patch flow waits for approval;
- run applies patches through `ApplyPatchTool`;
- Python patches are verified with `python -m py_compile`;
- report artifacts are created after mutating run.

Stubs/problems:

- active sessions are in-memory only;
- no authentication;
- no persistent approval database;
- `SessionStore` still delegates plan/propose to `PatchGenerator`, where routing must become Ollama-first.

### `src/complex_agent/app.py`

Purpose: shared runtime container.

Main behavior:

- resolves `project_root`;
- creates `ApprovalGate`, `SafetyPolicy`, `ToolRegistry`, `Planner`, `Verifier`, event bus;
- lazily creates SQLite/artifact stores;
- runs Phase 1 `AgentRuntime.run_plan` for CLI/audit/review flows.

Working behavior:

- lazy storage prevents read-only commands from creating `.agent`;
- shell/tools receive `ToolContext(project_root, safety)`.

Risks/gaps:

- CLI `run/review/audit` still use the generic Phase 1 planner, not the new web `PatchGenerator` flow;
- storage is local to selected root, so generated `.agent` must be ignored and not committed.

### `src/complex_agent/core/`

Purpose: task, state, observation, result, status, mode models.

Working behavior:

- Pydantic/dataclass-style task lifecycle is adequate for MVP.

Stubs:

- `agent_loop.py` is minimal and not the primary browser app loop.

### `src/complex_agent/execution/`

Purpose: executor and execution policies.

Working behavior:

- `executor.py` calls tools through registry and annotates observations.

Stubs:

- rollback manager is not real rollback yet;
- retry/timeout policies are thin MVP pieces.

### `src/complex_agent/tools/`

Purpose: typed/safe tool system.

Main files:

- `base_tool.py`, `tool_result.py`, `registry.py`, `defaults.py`.
- `filesystem/`: list/read/search/diff/apply patch.
- `shell/shell_tool.py`: allowlisted command execution.
- `git/`: status/diff/branch; commit is disabled.
- `code/`, `project/`: lint/test/build/project diagnostics tools.
- `web/`, `mcp/`: placeholders/future tools.

Working behavior:

- no tool is called directly from UI;
- `ToolRegistry.run()` validates input and invokes tool;
- `ApplyPatchTool` parses unified diff and checks target writes through `FileGuard`;
- `ShellTool` uses `CommandGuard` and runs with `cwd=context.project_root`;
- `SearchFilesTool` is safety-filtered.

Risks:

- patch parser is intentionally simple and supports a limited subset of unified diffs;
- shell command splitting is simple (`command.split()`), so verification paths with spaces are not supported;
- future web/MCP tools must stay disabled or behind safety.

### `src/complex_agent/safety/`

Purpose: filesystem, command, approval, and secret controls.

Main files:

- `file_guard.py`: selected-root enforcement, forbidden names/segments/suffixes, size limit.
- `command_guard.py`: allowlist/denylist for shell commands.
- `secrets_guard.py`: redaction.
- `approval_gate.py`: task/step/action approval state.
- `safety_policy.py`: facade used by tools.

Working behavior:

- blocks `.env`, `.agent`, `.venv`, `.git`, `__pycache__`, `node_modules`, private keys, secret/token paths;
- blocks path escape outside selected root;
- blocks destructive Windows/PowerShell and git commands;
- requires approval for mutating actions in review-style flows;
- redacts command/file output.

Risks:

- symlink escape depends on `Path.resolve()` and should stay covered by tests;
- Docker volume safety depends on mounting only intended workspace;
- command allowlist must remain narrow.

### `src/complex_agent/llm/`

Purpose: provider boundary.

Main files:

- `provider.py`: provider interface.
- `ollama_provider.py`: local HTTP Ollama API provider.
- `mock_provider.py`, `openai_provider.py`: MVP placeholders/adapters.

Working behavior:

- Ollama uses `GET /api/tags` for model list/reachable;
- Ollama uses `POST /api/generate` for generation;
- model selection priority is implemented;
- generation check exists.

Gaps:

- no streaming;
- no robust JSON repair beyond one parser path;
- provider errors are surfaced but not deeply classified.

### `src/complex_agent/codegen/`

Purpose: proposed patch generation.

Current state:

- `patch_generator.py` can use Ollama for unknown tasks;
- it can validate proposed patches before returning them;
- it still contains deterministic calculator routing.

Problem:

- deterministic routing must not be default when Ollama is available. This is the main behavior to fix.

Required fix:

- add `ollama_patch_generator.py`;
- make default web/API flow use Ollama-first;
- keep calculator deterministic behavior only under explicit demo/test fallback.

### `src/complex_agent/skills/`

Purpose: deterministic workflows.

Current deterministic skill:

- `python_calculator_skill.py`.

Why it exists:

- stable demo/test fixture;
- works without Ollama.

Problem:

- it must not be the default brain for normal tasks when Ollama is reachable.

Required fix:

- explicit demo mode/env/test injection only;
- default UI/API route should use Ollama if reachable, including calculator-like prompts.

### `src/complex_agent/web/`

Purpose: static browser UI.

Main elements:

- left sidebar;
- project selection form;
- task history;
- centered task feed;
- right floating `Среда` card;
- bottom composer;
- plan/diff/approval/result/report cards.

Working buttons:

- `Новый чат`: clears local UI/session state.
- `Выбрать папку`: shows manual folder input.
- `Применить`: calls `POST /api/project/select`.
- `Отмена`: hides folder form.
- quick prompts: submit predefined tasks.
- send button: creates plan.
- `Предложить изменения`: calls task propose endpoint.
- `Запустить цель`: proceeds by state.
- `Показать Diff`: expands/shows current diff in cards.
- `Подтвердить`: calls approve then run.
- `Отклонить`: calls reject.
- `Проверить`: submits audit-style check prompt.
- `Открыть Diff`: shows current diff or empty state.
- refresh: reloads status/workspace/project.
- `Создать коммит`: disabled by design.

Gaps/risks:

- static UI has no authentication;
- no live editor/Monaco;
- no full browser e2e click suite yet;
- no persistent chat history after backend restart.

### `src/complex_agent/desktop/`

Purpose: local desktop wrapper.

Main file:

- `app.py`: finds a free port, starts uvicorn/FastAPI on localhost, opens `pywebview` window.

Working behavior:

- uses same static UI as browser;
- default title `Локальный агент`;
- default window size `1400x900`, min `1100x720`;
- stops backend on window close.

Gaps:

- no packaged `.exe`;
- desktop availability depends on optional `pywebview` extra.

### `src/complex_agent/storage/`

Purpose: durable run history and artifacts.

Working behavior:

- SQLite and artifact directories are lazy;
- mutating run writes reports under selected root `.agent/artifacts`.

Gaps:

- no retention cleanup;
- no persistent task/session store for web sessions.

### `src/complex_agent/verification/`

Purpose: result checks.

Working behavior:

- verifies failed observations, forbidden changed files, unapproved changed files, final report error visibility.

Gaps:

- specialized build/test parsing is limited;
- py_compile verification is currently selected by web session logic, not a general verifier planner.

### `tests/`

Purpose: unit/API/static coverage.

Working coverage:

- API endpoints;
- CLI read-only side effects;
- filesystem/search safety;
- command guard;
- verifier;
- Ollama provider with mocks;
- desktop module/CLI;
- web static safety.

Gaps:

- no true browser DOM click automation;
- no Docker tests yet;
- real Ollama smoke is manual/scripted, not CI.

### `docs/`

Purpose: architecture, audit, phase reports, local app docs.

Gaps:

- Docker docs are missing before this final hardening work;
- final Ollama-first report still required.

### `config/`

Purpose: YAML configuration.

Working behavior:

- `models.yaml` includes Ollama settings;
- env overrides exist for `OLLAMA_BASE_URL` and `OLLAMA_MODEL`.

Gaps:

- config is not yet the single source for all runtime flags;
- demo fallback flag should be explicit.

### `scripts/`

Purpose: helper scripts.

Current files:

- test/run/format/demo helpers;
- desktop launcher.

Missing:

- Docker build/run scripts.

## 3. Runtime flow

Current browser/desktop flow:

```text
UI -> API routes -> SessionStore -> PatchGenerator
   -> OllamaProvider or deterministic skill
   -> proposed patch stored in TaskSession
   -> approval endpoint -> ApprovalGate
   -> run endpoint -> ApplyPatchTool -> ShellTool -> artifact report
```

More detailed:

- task is created in `SessionStore.create_plan()` through `AgentRuntime.create_task()`;
- plan is created by `PatchGenerator.create_plan()`;
- proposed diff is created by `SessionStore.propose()` through `PatchGenerator.propose()`;
- approval is recorded in `ApprovalGate` through `SessionStore.approve()`;
- patch is applied in `SessionStore._run_proposed_patch()` through `runtime.registry.run("apply_patch", ...)`;
- shell verification is run through `runtime.registry.run("shell", ...)`;
- report is written through `runtime.artifacts.write_text()`.

Current CLI `run/review/audit` flow:

```text
CLI -> AgentRuntime.run -> Planner -> Executor -> ToolRegistry -> Verifier -> FinalReportBuilder
```

This is safe but less capable than the browser Ollama flow.

Required final flow:

```text
UI -> API -> SessionStore -> OllamaPlanner -> OllamaPatchGenerator
   -> validation -> approval -> ApplyPatchTool -> ShellTool -> report
```

## 4. API endpoints

| Method | Path | Purpose | Read-only | Creates `.agent` | Approval | Safety checks |
|---|---|---|---:|---:|---:|---|
| GET | `/health` | local health | yes | no | no | none needed |
| GET | `/` | static UI | yes | no | no | static file only |
| GET | `/api/status` | project/tool/LLM status | yes | no | no | no file write |
| GET | `/api/tools` | tool list/status | yes | no | no | registry metadata |
| GET | `/api/project` | selected root | yes | no | no | path exists metadata |
| POST | `/api/project/select` | switch selected root | mutates session only | no | no | directory existence |
| GET | `/api/workspace` | workspace summary | yes | no | no | `list_files`, `git_*`, `FileGuard` |
| GET | `/api/files` | safe file list | yes | no | no | `ListFilesTool`, `FileGuard` |
| GET | `/api/files/preview` | safe file read | yes | no | no | `FileGuard`, `ReadFileTool`, redaction |
| GET | `/api/git/diff` | safe git diff | yes | no | no | `GitDiffTool`, redaction |
| POST | `/api/chat` | chat + plan | session mutation | no | no | plan only |
| POST | `/api/tasks/plan` | create task plan | session mutation | no | no | LLM/provider only |
| POST | `/api/tasks/{task_id}/propose` | propose diff | session mutation | no | no | patch validation, `FileGuard`, redaction |
| POST | `/api/tasks/{task_id}/approve` | approve pending action | session mutation | no | yes | known task/step/action |
| POST | `/api/tasks/{task_id}/reject` | reject pending action | session mutation | no | yes | known task/step/action |
| POST | `/api/tasks/{task_id}/run` | apply approved patch/check/report | mutating | yes | must be approved | `ApplyPatchTool`, `ShellTool`, guards |
| GET | `/api/tasks/{task_id}` | task state | yes | no | no | redacted state |
| GET | `/api/tasks/{task_id}/events` | raw session events | yes | no | no | session only |
| GET | `/api/tasks/{task_id}/diff` | proposed/current diff | yes | no | no | stored diff only |
| GET | `/api/tasks/{task_id}/report` | final report | yes | no | no | report path from session |
| GET | `/api/tasks/{task_id}/timeline` | UI event timeline | yes | no | no | session only |

## 5. UI analysis

The UI is a static HTML/CSS/JS app. It uses no React/Vue build pipeline.

Current layout matches the requested direction:

- dark theme;
- left sidebar;
- central feed;
- right `Среда` floating card;
- bottom composer;
- no permanent file explorer;
- no permanent bottom workbench panel;
- no dashboard page.

Button behavior:

| Button | Current behavior | Status |
|---|---|---|
| Новый чат | clears feed/session state | works |
| Выбрать папку | opens inline path form | works |
| Применить папку | calls `/api/project/select` | works |
| Отмена выбора папки | hides form | works |
| quick prompts | submit predefined task | works |
| отправить задачу | calls `/api/tasks/plan` | works |
| Предложить изменения | calls `/api/tasks/{id}/propose` | works |
| Запустить цель | state-aware plan/propose/run | works |
| Показать Diff | details block in diff card | works |
| Подтвердить | calls approve then run | works |
| Отклонить | calls reject | works |
| Проверить | submits audit prompt | works |
| Открыть Diff | shows stored diff or empty message | works |
| Обновить status | reloads status/project/workspace | works |
| Создать коммит | disabled and reports MVP limit | disabled by design |

Known UI gaps:

- no live DOM click test suite;
- no file editor;
- no long-running task streaming;
- chat/session state is lost on backend restart.

## 6. Ollama integration

Provider:

- file: `src/complex_agent/llm/ollama_provider.py`;
- default base URL: `http://127.0.0.1:11434`;
- model/env config: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `config/models.yaml`;
- reachable check: `GET /api/tags`;
- generation check: `POST /api/generate`.

Model selection priority:

1. `qwen3-coder:30b`
2. `qwen2.5-coder:14b`
3. `qwen2.5-coder:7b-instruct`
4. `qwen3:8b`
5. first available model

Current fallback problem:

- `PatchGenerator` can route calculator prompts to deterministic skill;
- this is wrong for default behavior when Ollama is reachable because it makes the app look like an AI agent while using a template.

Required fix:

- add real `OllamaPlanner`;
- add real `OllamaPatchGenerator`;
- default `PatchGenerator` becomes Ollama-first;
- deterministic skills become explicit demo/test-only.

## 7. Deterministic skills

Current deterministic skills:

- `PythonCalculatorSkill`.

Current connection point:

- `PatchGenerator.supports()`, `create_plan()`, and `propose()`.

Why this is not acceptable as default:

- it bypasses LLM reasoning;
- it works only for a hardcoded task;
- it can mask broken Ollama behavior.

What to keep:

- deterministic calculator as a test fixture/demo fallback.

What to change:

- require explicit demo fallback flag or injected test configuration;
- do not use it automatically in normal UI/API when Ollama is reachable.

## 8. Safety analysis

### FileGuard

Enforces selected root and forbidden paths. It resolves paths and rejects escape from
`project_root`. It blocks `.env`, credentials, private-key suffixes, `.agent`, `.git`,
`.venv`, `venv`, `node_modules`, `__pycache__`, and secret/token path segments.

### CommandGuard

Allows only narrow command prefixes such as git status/diff/log/show, `rg`, pytest,
`python -m pytest`, `python -m py_compile`, ruff/mypy, and dotnet build/test. It blocks
destructive fragments like `git reset --hard`, `git clean`, `rm -rf`, `del /s`,
`rmdir /s`, `Remove-Item`, `Invoke-Expression`, `iwr`, `curl`, and `powershell`.

### SecretsGuard

Redacts secret-like content from outputs and context. Patch validation rejects patch text
that changes after redaction.

### ApprovalGate

Stores approved/rejected task/step/action tuples. Proposed patches are not applied until
the matching approval exists.

### ApplyPatchTool

Parses unified diffs and writes only through `FileGuard.validate_write()`. It does not
support deletion in MVP.

### ShellTool

Runs allowlisted commands with `cwd=context.project_root`. It captures and redacts output.

### Selected project root

Project root is selected at app startup or through `/api/project/select`. All runtime
tools use that root through `ToolContext`.

### Docker restrictions

Docker is not present yet. It must be added so the container sees only `/workspace`, not
the host disk. Shell cwd inside Docker must remain `/workspace`.

## 9. Docker

Current state: Docker files are missing.

Required Docker implementation:

- `Dockerfile`;
- `docker-compose.yml`;
- `.dockerignore`;
- `scripts/docker_build.ps1`;
- `scripts/docker_run.ps1`;
- `docs/docker.md`.

Container requirements:

- Python 3.12;
- install package;
- run app server on `0.0.0.0:8765`;
- non-root user if practical;
- exclude `.venv`, `.agent`, `__pycache__`, `.git`;
- mount one selected workspace to `/workspace`;
- use `AGENT_PROJECT_ROOT=/workspace`;
- support host Ollama through `http://host.docker.internal:11434`;
- optional Ollama service/profile documented, not auto-pulling models.

Docker safety rule:

```text
The container can only see the mounted workspace volume.
```

## 10. Desktop app

Current state: desktop app exists.

Launch:

```powershell
python -m complex_agent.main desktop --project F:\1
```

Behavior:

- starts uvicorn/FastAPI on localhost;
- opens same static UI in `pywebview`;
- window title: `Локальный агент`;
- default size: `1400x900`;
- min size: `1100x720`.

Gaps:

- no packaged installer/exe;
- depends on optional `desktop` extra.

## Stubs / placeholders / incomplete behavior

- `api/auth.py`: placeholder, no auth.
- `tools/mcp/`: placeholder.
- `subagents/`: placeholder.
- `memory/vector_memory.py`, `long_term_memory.py`: future placeholders.
- `execution/rollback_manager.py`: not full rollback.
- `tools/web/`: placeholder/future web tools.
- `openai_provider.py`: provider boundary placeholder, not active default.
- CLI `run/review` uses Phase 1 planner rather than Ollama-first plan/diff flow.
- `PatchGenerator` still mixes deterministic skill and Ollama behavior.
- No Docker files before final hardening.
- No browser e2e click automation.

## Safety risks

- Writing outside selected folder: mitigated by `FileGuard`, but must be covered in Docker too.
- Shell commands: mitigated by `CommandGuard`, but allowlist must stay narrow.
- `.env` leakage: mitigated by `FileGuard` and `SecretsGuard`; preview/list/search tests must remain.
- Bad LLM patch: mitigated by validation, forbidden path checks, secret checks, and approval.
- Docker volume: if user mounts too broad a directory, the container can access it; docs/scripts must mount only intended workspace.
- Interactive commands: should not be selected for verification; `CommandGuard` should not allow them.
- Deletion: `ApplyPatchTool` does not support file deletion in MVP.
- Deterministic fallback: can mask broken LLM behavior unless explicitly gated.

## Required fixes before final MVP

1. Add `src/complex_agent/planning/ollama_planner.py`.
2. Add `src/complex_agent/codegen/ollama_patch_generator.py`.
3. Make normal UI/API task planning and patch proposal Ollama-first.
4. Disable deterministic calculator routing by default when Ollama is reachable.
5. Keep deterministic calculator only for explicit demo/test fallback.
6. Fail clearly when Ollama is unavailable for normal coding tasks.
7. Strengthen patch validation around markdown fences, absolute paths, traversal, forbidden files, and secret-like content.
8. Keep safe verification restricted to allowlisted non-interactive commands.
9. Add Dockerfile, docker-compose, docker scripts, and Docker docs.
10. Add/adjust tests for Ollama-first routing, no deterministic fallback, Docker files, UI handlers, and safety.
11. Run real Ollama `snake.py` smoke through plan -> diff -> approval -> run -> py_compile.
12. Run sandbox smoke for absolute path, traversal, and `.env`.
13. Run server and desktop smoke.
14. Create `docs/final_ollama_agent_mvp_report.md`.
