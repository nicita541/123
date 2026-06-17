# Final Ollama Coding Agent MVP Report

Date: 2026-06-18  
Repository: `F:\aiAgent`  
Smoke workspace: `F:\1`

## Summary

The application now uses Ollama as the default planning and patch-generation path for
normal coding tasks. The deterministic calculator skill remains available only when the
explicit demo fallback flag is enabled or a test injects demo mode.

Final runtime flow:

```text
Task -> OllamaPlanner -> validated JSON plan -> OllamaPatchGenerator
     -> strict unified diff validation -> UI Diff -> approval
     -> ApplyPatchTool -> ShellTool safe verification -> report
```

No file is written before approval. Ollama never receives direct filesystem or shell
access and never applies a patch itself.

## What changed

- Added `src/complex_agent/planning/ollama_planner.py`.
- Added `src/complex_agent/codegen/ollama_patch_generator.py`.
- Changed `PatchGenerator` to Ollama-first routing.
- Added explicit `AGENT_ENABLE_DEMO_FALLBACK=1` gate for deterministic calculator routing.
- Added one strict retry for invalid plan JSON and invalid patch output.
- Rejected markdown-fenced patches, explanations instead of diff, absolute paths, traversal,
  forbidden paths, and secret-like patch content.
- Passed the Ollama plan into patch-generation context.
- Updated UI model selector from the real `/api/status.ollama_models` list.
- Added Dockerfile, compose file, ignore file, scripts, documentation, and tests.
- Preserved the existing desktop app and same shared static UI.
- Created `docs/FULL_SYSTEM_ANALYSIS.md` before implementation changes.

## Previous incomplete behavior

Before this hardening, calculator-like tasks could route directly to a deterministic
template even when Ollama was available. That made the app useful as a demo but not a
general AI coding agent. The deterministic path is now opt-in only.

Other known placeholders remain isolated and inactive: MCP, subagents, vector memory,
long-term memory, web tools, full rollback, and authentication.

## Ollama-first flow

Planner behavior:

- sends task, selected project root, and safe file summary to Ollama;
- requires JSON matching the plan schema;
- validates paths and verification commands;
- retries once with a stricter JSON-only prompt;
- fails clearly if Ollama remains invalid or unavailable.

Patch behavior:

- sends task, plan, and safe file summary to Ollama;
- requires raw unified diff only;
- rejects markdown fences and explanatory text;
- validates every path with `FileGuard`;
- stores the proposed diff without applying it;
- applies only after a matching approval.

Current Ollama status:

```text
provider=ollama
base_url=http://127.0.0.1:11434
selected_model=qwen3-coder:30b
reachable=True
generation_check=True
models=qwen3:8b, qwen2.5-coder:7b-instruct, qwen2.5-coder:14b, qwen3-coder:30b
```

## Real snake.py smoke

Task:

```text
Создай snake.py: простая консольная змейка на Python без внешних зависимостей. Не запускай игру интерактивно, только проверь синтаксис.
```

Observed result:

```text
used_provider=ollama
selected_model=qwen3-coder:30b
generation_check=True
plan_created=True
plan_status=planned
proposed_status=waiting_approval
proposed_diff_has_snake=True
before_approve_snake_exists=False
run_before_status=waiting_approval
approve_status=approved
final_status=completed
after_approve_run_snake_exists=True
used_skill=ollama
used_deterministic_fallback=False
final_report_exists=True
verification_contains_py_compile=True
py_compile_ok=True
```

External syntax verification:

```powershell
F:\aiAgent\.venv\Scripts\python.exe -m py_compile F:\1\snake.py
```

Result: passed.

`F:\1\snake.py` remains as generated smoke output outside the repository.

## Sandbox

Selected project root: `F:\1`.

Results:

```text
outside_patch_blocked=True
traversal_patch_blocked=True
env_preview_status=403
env_secret_exposed=False
outside_test_exists=False
outside_exists=False
```

The temporary `.env` used for the test was removed after verification.

Safety path:

- list/read/search use `FileGuard`;
- patch validation and `ApplyPatchTool` use `FileGuard.validate_write`;
- shell uses `CommandGuard` and `cwd=selected project root`;
- outputs pass through `SecretsGuard` redaction;
- no raw shell/write/apply-patch/arbitrary-git endpoint exists.

## Docker

Added:

- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- `scripts/docker_build.ps1`
- `scripts/docker_run.ps1`
- `docs/docker.md`

Docker configuration:

- Python 3.12 slim image;
- non-root `agent` user;
- backend on port 8765;
- selected workspace mounted only at `/workspace`;
- `AGENT_PROJECT_ROOT=/workspace`;
- host Ollama through `http://host.docker.internal:11434`;
- optional compose `ollama` profile.

Validation:

```text
docker --version: Docker 29.4.0
docker compose config: passed
docker build -t complex-ai-agent:local .: passed
docker_health_status=ok
docker_project_root=/workspace
```

## Desktop app

Command:

```powershell
python -m complex_agent.main desktop --project F:\1
```

Smoke result:

```text
desktop_process_exited=False
desktop_health_status=ok
desktop_index_has_ui=True
```

Desktop mode uses the same `index.html`, `app.js`, and `styles.css` as browser mode.

## Browser server smoke

```text
server_health_status=ok
server_index_has_ui=True
server_status_model=qwen3-coder:30b
server_generation_check=True
```

## Button status

Verification method: static handler tests plus API/server/desktop smoke.

```text
Новый чат: works
Выбрать папку: works
Применить папку: works
Отмена: works
quick prompts: works
Отправить: works
Предложить изменения: works
Запустить цель: works
Показать Diff: works
Подтвердить: works
Отклонить: works
Проверить: works
Открыть Diff: works
Обновить status: works
Создать коммит: disabled_by_design
```

## Test results

```text
.venv\Scripts\python.exe -m pytest
81 passed, 1 warning in 88.28s

.venv\Scripts\python.exe -m unittest discover
Ran 77 tests in 84.867s
OK

.venv\Scripts\python.exe -m compileall -q src tests
passed
```

CLI smoke:

```text
status: exit code 0
tools: exit code 0
plan "Audit this project": exit code 0
```

The only test warning is the existing Starlette `TestClient` deprecation warning for the
bundled `httpx` compatibility import.

## Remaining MVP limits

- No authentication; server is local-only by default.
- Web sessions and approvals are in-memory and are lost after backend restart.
- No full browser DOM click automation in this environment.
- No packaged desktop `.exe` or installer.
- Docker safety still depends on the user mounting only the intended project folder.
- Patch parser supports a constrained unified-diff subset and does not support deletion.
- Shell command parsing does not support verification file paths containing spaces.
- CLI `run/review/audit` retains the Phase 1 planner; the full Ollama-first task workflow is
  the browser/desktop API path.
- MCP, subagents, vector memory, long-term memory, cloud execution, auto-commit, and auto-push
  remain out of scope.
