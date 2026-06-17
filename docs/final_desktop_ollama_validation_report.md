# Final Desktop + Ollama Validation Report

Date: 2026-06-17  
Repository: `F:\aiAgent`  
Smoke project root: `F:\1`

## Summary

The local task-centered coding-agent MVP now supports:

- optional local Ollama provider for generic planning and patch proposal;
- deterministic calculator skill as a non-LLM fallback;
- approval-gated patch application through `ApplyPatchTool`;
- generic Python patch verification through `python -m py_compile`;
- desktop app launch through `pywebview`;
- selected-root sandbox for file preview, patch validation, patch application, git status/diff, and shell checks.

The required generic Ollama smoke passed end-to-end:

```text
before_exists=False
after_propose_exists=False
proposed_diff_has_snake=True
approve_status=approved
final_status=completed
after_approved_run_exists=True
py_compile_ok=True
used_provider=ollama
used_deterministic_fallback=False
```

## Ollama Status

Direct tags check:

```powershell
curl.exe --max-time 30 http://127.0.0.1:11434/api/tags
```

Result: OK.

Available models:

- `qwen3:8b`
- `qwen2.5-coder:7b-instruct`
- `qwen2.5-coder:14b`
- `qwen3-coder:30b`

Selected model by priority:

```text
qwen3-coder:30b
```

Direct generation check:

```powershell
curl.exe --max-time 120 -H "Content-Type: application/json" --data-binary "@F:\Temp\ollama-generate-payload.json" http://127.0.0.1:11434/api/generate
```

Result:

```json
{"model":"qwen3-coder:30b","response":"OK","done":true,"done_reason":"stop"}
```

CLI status result:

```text
project: F:\aiAgent
tools: 16
LLM provider: ollama
Ollama base URL: http://127.0.0.1:11434
Ollama model: qwen3-coder:30b
Ollama reachable: yes
Ollama generation check: yes
Ollama models: qwen3:8b, qwen2.5-coder:7b-instruct, qwen2.5-coder:14b, qwen3-coder:30b
```

## Generic Ollama Workflow

Task:

```text
Создай snake.py: простая консольная змейка на Python без внешних зависимостей. Не запускай интерактивную игру, только проверь синтаксис.
```

API smoke path:

```text
POST /api/tasks/plan
POST /api/tasks/{task_id}/propose
POST /api/tasks/{task_id}/run
POST /api/tasks/{task_id}/approve
POST /api/tasks/{task_id}/run
```

Observed result:

```text
before_exists=False
after_propose_exists=False
proposed_status=waiting_approval
proposed_diff_has_snake=True
run_before_status=waiting_approval
approve_status=approved
final_status=completed
after_approved_run_exists=True
used_provider=ollama
selected_model=qwen3-coder:30b
generation_check=True
used_skill=ollama
used_deterministic_fallback=False
verification_contains_py_compile=True
report_path=F:\1\.agent\artifacts\artifact_a63e2a84043d.md
```

External verification:

```powershell
.venv\Scripts\python.exe -m py_compile F:\1\snake.py
```

Result:

```text
py_compile_ok=True
```

## Sandbox Checks

Selected root:

```text
F:\1
```

Explicit absolute-path patch:

```text
outside_patch_blocked=True
outside_patch_error=Path escapes project root: F:\outside_test.txt
outside_test_exists=False
```

Explicit path traversal patch:

```text
traversal_patch_blocked=True
traversal_patch_error=Path escapes project root: F:\outside.txt
outside_exists=False
```

Forbidden `.env` preview:

```text
env_preview_status=403
env_secret_exposed=False
```

## Server Smoke

Command:

```powershell
.venv\Scripts\python.exe -m complex_agent.main serve --project F:\1 --host 127.0.0.1 --port 8765
```

Checked endpoints:

- `/health`
- `/`
- `/api/status`
- `/api/project`
- `/api/workspace`

Result:

```text
health_status=ok
index_has_ui=True
api_status_provider=ollama
api_status_model=qwen3-coder:30b
api_status_generation_check=True
project_root=F:\1
workspace_status=ready
```

## Desktop App

Dependency installation:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[desktop]"
```

Result: OK, installed `pywebview-6.2.1`.

Desktop smoke command:

```powershell
.venv\Scripts\python.exe -m complex_agent.main desktop --project F:\1 --host 127.0.0.1 --port 8766
```

Result:

```text
desktop_process_exited=False
desktop_health_status=ok
desktop_index_has_ui=True
```

The desktop app uses the same `index.html`, `app.js`, and `styles.css` as browser mode.

## Button Smoke Report

Verification method: static handler checks in `tests/web/test_web.py`, API smoke, server smoke, and desktop launch smoke. The in-app Browser JS-control tool was not available in this session, so button checks were not performed through live DOM clicking.

```text
Новый чат: works
Выбрать папку: works
Применить выбранную папку: works
Отмена выбора папки: works
quick prompt calculator: works
отправить сообщение: works
Предложить изменения: works
Показать Diff: works
Подтвердить: works
Отклонить: works
Запустить цель: works
Проверить: works
Открыть Diff в карточке Среда: works
Обновить status: works
Создать коммит: disabled_by_design
```

## Test Results

Focused test block:

```text
python -m unittest tests.llm.test_ollama_provider tests.codegen.test_patch_generator tests.api.test_api tests.web.test_web tests.safety.test_safety_policy tests.desktop.test_desktop_app
Ran 51 tests in 103.921s
OK
```

Full pytest:

```text
.venv\Scripts\python.exe -m pytest
76 passed, 1 warning in 68.90s
```

Unittest discover:

```text
.venv\Scripts\python.exe -m unittest discover
Ran 72 tests in 78.884s
OK
```

Compileall:

```text
.venv\Scripts\python.exe -m compileall -q src tests
passed
```

CLI checks:

```text
.venv\Scripts\python.exe -m complex_agent.main --project . status
exit code 0

.venv\Scripts\python.exe -m complex_agent.main --project . tools
exit code 0

.venv\Scripts\python.exe -m complex_agent.main --project . plan "Audit this project"
exit code 0
```

## Remaining MVP Limits

- No auth; server is local-only by default.
- No cloud execution.
- No direct browser endpoints for arbitrary shell, raw writes, raw patch apply, arbitrary git command, auto-commit, or auto-push.
- No MCP, subagents, vector memory, long-term memory, Monaco editor, WPF UI, or packaged `.exe`.
- UI live-click verification was not available through the in-app browser JS-control tool in this session; behavior was verified through static handlers and API/desktop/server smoke.
- Demo output under `F:\1` is generated runtime output and is not part of the repo source.
