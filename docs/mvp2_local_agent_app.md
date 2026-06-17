# MVP 2 Local Agent App

## What Is Implemented

MVP 2 adds a local browser app on top of the Phase 1 safe runtime:

- FastAPI backend served from `src/complex_agent/api/`;
- static HTML/CSS/JS frontend served from `src/complex_agent/web/`;
- in-memory chat and task sessions;
- plan creation through the existing planner;
- execution through `AgentRuntime`, `Executor`, `ToolRegistry`, `SafetyPolicy`, and `ApprovalGate`;
- local-only default binding to `127.0.0.1:8765`;
- no direct file-write endpoint and no direct shell-command endpoint.

## How To Run

From `F:\aiAgent`:

```powershell
.venv\Scripts\python.exe -m complex_agent.main serve --project . --host 127.0.0.1 --port 8765
```

Then open:

```text
http://127.0.0.1:8765
```

The server is intended for local use. MVP 2 does not include authentication or a production security model.

## Интерфейс

MVP 2.1 обновляет статический интерфейс без изменения backend-контрактов:

- верхняя панель показывает название `Комплексный ИИ-агент`, локальный режим, путь проекта, состояние сервера и режим работы;
- левая панель содержит факты проекта, навигацию, список доступных инструментов и список задач;
- центральная область работает как чат: пользователь описывает задачу, агент отвечает планом, а основные действия доступны через кнопки `Отправить`, `Создать план`, `Выполнить план` и `Остановить`;
- правая панель показывает текущий план, ожидающие подтверждения, изменённые файлы и итоговый результат;
- нижняя панель содержит вкладки `События`, `Проверки`, `Diff/Различия` и `Отчёт`.

Интерфейс использует только `index.html`, `styles.css` и `app.js`; React/Vue/Svelte и сборочный pipeline не добавлены.

## Endpoints

- `GET /health`: backend health and local-only marker.
- `GET /api/status`: project root, default mode, enabled tool count, `.agent` presence, latest run summary.
- `GET /api/tools`: tools with `enabled`, `disabled`, or `internal` status.
- `POST /api/chat`: creates or continues a chat session and returns a plan preview.
- `POST /api/tasks/plan`: creates a task session and plan.
- `POST /api/tasks/{task_id}/run`: runs the stored plan through the safe runtime.
- `POST /api/tasks/{task_id}/approve`: approves a known pending step/action.
- `POST /api/tasks/{task_id}/reject`: rejects a known pending step/action.
- `GET /api/tasks/{task_id}`: task state.
- `GET /api/tasks/{task_id}/events`: session events.
- `GET /api/tasks/{task_id}/report`: final report text if available.
- `GET /api/tasks/{task_id}/diff`: captured diff if available.

## Workflow

1. Start the local server.
2. Open the UI in a browser.
3. Enter a task in chat or use Create Plan.
4. Review the generated plan.
5. Press Run.
6. If approval is required, approve or reject the pending step.
7. Inspect events, verifier output, diff, changed files, and final report.

## Safety Guarantees

- Read-only endpoints do not create `.agent`, SQLite history, or artifacts.
- Planning does not mutate files.
- File writes only happen through approved mutating tools.
- Shell execution only happens through `ShellTool` and `CommandGuard`.
- Search uses `FileGuard`; forbidden files are not exposed.
- Tool output is redacted through the existing safety layer.
- The UI has no direct file-write or shell-command endpoint.

## Limits

- Sessions are in memory and are lost when the backend restarts.
- The planner remains deterministic and conservative.
- No production authentication is included.
- Approval support is minimal and task-session scoped.
- The frontend is intentionally plain HTML/CSS/JS with no build step.

## Not In MVP 2

- LLM planner integration.
- Subagents.
- MCP.
- Vector memory.
- Long-term memory.
- Web authentication.
- Cloud deployment.
- GitHub integration.
- Auto-commit or auto-push.
- React/Vue frontend.
- Production multi-user mode.
