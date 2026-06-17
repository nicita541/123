# Final MVP Completion Report

## Что исправлено

- UI заменён на чистый UTF-8 русский task-centered workspace.
- Добавлен manual выбор рабочей папки через `/api/project` и `/api/project/select`.
- Active project root пересоздаёт runtime/session и не создаёт `.agent`.
- Основной workflow работает как `task -> plan -> proposed diff -> approval -> ApplyPatchTool -> self-test -> final report`.
- Кнопки `Новый чат`, quick prompts, `Предложить изменения`, `Запустить цель`, `Подтвердить`, `Отклонить`, `Проверить`, `Открыть diff`, `Выбрать папку` подключены к рабочим handlers.
- Ollama status дополнен списком локальных моделей через `/api/tags`.
- Deterministic calculator skill оставлен fallback-first и работает без Ollama.
- Тесты исправлены на реальные русские UTF-8 строки вместо mojibake.

## Выбор папки

Пользователь вводит путь вручную в sidebar. Backend валидирует, что путь существует и является директорией. После выбора:

- `AgentRuntime` создаётся заново для новой папки;
- chat/task sessions очищаются;
- `Workspace`, `Files`, `Git diff`, task plan/propose/run используют новый root;
- `.agent` не создаётся до реального mutating run/report.

## Sandbox root

Все операции ограничены выбранной папкой:

- file list/read/search/preview проходят `FileGuard`;
- patch validation и `ApplyPatchTool` блокируют escape outside root;
- shell запускается только с `cwd` selected project root и через `CommandGuard`;
- `.env`, `.agent`, `.venv`, `__pycache__`, secret/token/private-key paths скрываются или блокируются.

## Goal mode

Для calculator task:

1. Создаётся план.
2. Генерируется proposed diff.
3. До approve файл не создаётся.
4. После approve patch применяется через `ApplyPatchTool`.
5. Запускается `python calculator.py --self-test`.
6. Создаётся финальный отчёт.

Для неизвестной задачи без Ollama файлы не меняются, а UI показывает понятную ошибку/fallback.

## Ollama

Status содержит provider, base URL, selected model, reachable flag и `ollama_models`. Если Ollama недоступен, calculator demo продолжает работать через deterministic skill.

Ollama не пишет файлы напрямую. Он может только предложить structured plan или unified diff, который проходит validation, safety checks и approval.

## Проверенные кнопки

- `Новый чат`
- `Выбрать папку`
- quick prompt buttons
- composer send
- access selector
- `Предложить изменения`
- `Запустить цель`
- `Подтвердить`
- `Отклонить`
- `Проверить`
- `Открыть diff`
- `Обновить`

## Тесты

Финальный набор проверок должен включать:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m unittest discover
.venv\Scripts\python.exe -m compileall -q src tests
.venv\Scripts\python.exe -m complex_agent.main --project . status
.venv\Scripts\python.exe -m complex_agent.main --project . tools
.venv\Scripts\python.exe -m complex_agent.main --project . plan "Audit this project"
```

Server smoke:

```text
GET /health
GET /
GET /api/status
GET /api/project
GET /api/workspace
```

Calculator smoke:

```powershell
.venv\Scripts\python.exe calculator.py --self-test
```

## Оставшиеся ограничения

- Нет production auth; сервер рассчитан на local-only usage.
- Выбор папки реализован manual path input, не native OS picker.
- UI не является полноценной IDE и не содержит Monaco/editor.
- Rollback, MCP, subagents, vector memory, GitHub integration, auto-commit, auto-push и cloud mode не входят в этот MVP.
- Demo-created `calculator.py` считается generated output, если его явно не решено оставить как source.
