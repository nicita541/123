# MVP 3: Local Coding-Agent Workspace

## Что реализовано

MVP 3 превращает Local Agent App в локальный coding-agent workspace: чат, план, безопасный просмотр файлов, Diff, журнал, проверки, approvals и итоговый отчёт собраны в одном русскоязычном интерфейсе.

Это не копия брендинга Codex. В UI используется название `Локальный coding-агент`.

## Запуск

```powershell
.venv\Scripts\python.exe -m complex_agent.main serve --project . --host 127.0.0.1 --port 8765
```

Открыть:

```text
http://127.0.0.1:8765
```

Сервер по умолчанию локальный. MVP 3 не добавляет production auth и multi-user режим.

## Интерфейс

- Верхняя панель: путь проекта, git branch, статус сервера, режим и действия `Обновить`, `Проверить проект`, `Открыть отчёт`.
- Левая `Рабочая область`: вкладки `Файлы`, `Поиск`, `Изменения`, `Инструменты`.
- Центр: `Чат + задача`, статусы workflow, ввод задачи и кнопки `Отправить`, `Составить план`, `Выполнить`, `Остановить`.
- Правая панель: текущая задача, план выполнения, текущий шаг, подтверждения, риски и итог.
- Нижний `Workbench`: `Diff`, `Терминал`, `Проверки`, `Журнал`, `Отчёт`.

Файлы открываются только в read-only preview. Полноценный IDE editor не входит в MVP 3.

## Добавленные endpoints

- `GET /api/workspace`: summary рабочей области, project root, git branch, важные директории, files summary, changed files, tool counts.
- `GET /api/files`: безопасный список файлов проекта.
- `GET /api/files/preview?path=...`: безопасный preview файла.
- `GET /api/git/diff`: текущий Diff через существующий `git_diff` tool.
- `GET /api/tasks/{task_id}/timeline`: события задачи в удобном для UI виде.

Существующие endpoints `chat`, `plan`, `run`, `approve`, `reject`, `report`, `diff`, `status`, `tools` сохранены.

## Safety guarantees

- Нет endpoint для прямого `write_file`.
- Нет endpoint для прямого shell command execution.
- File list и preview проходят через `FileGuard`.
- `.env`, `.agent`, `.venv`, `__pycache__`, secret/token paths и private key files не показываются в списке файлов и не читаются через preview.
- Текстовые outputs проходят redaction через существующий safety layer.
- Read-only endpoints не создают `.agent`, SQLite или artifacts.
- Mutating execution остаётся только через `AgentRuntime`, `Executor`, `ToolRegistry`, `SafetyPolicy` и `ApprovalGate`.

## Ограничения

- Нет настоящего LLM planner.
- Нет автоматического исправления кода.
- Нет cloud mode, GitHub integration, MCP, subagents, vector memory или long-term memory.
- Нет multi-user auth.
- Нет dark theme, drag-and-drop, Monaco editor или полноценного IDE editor.
- Sessions остаются in-memory и теряются при restart backend.

## Проверка

Основная проверка для MVP 3:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m unittest discover
.venv\Scripts\python.exe -m compileall -q src tests
.venv\Scripts\python.exe -m complex_agent.main --project . status
.venv\Scripts\python.exe -m complex_agent.main --project . tools
.venv\Scripts\python.exe -m complex_agent.main --project . plan "Audit this project"
```
