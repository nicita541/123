# Local AI Coding Agent

Long-running local coding workspace with a native C# Avalonia desktop application, a
containerized FastAPI backend, and containerized Ollama. The agent plans work, proposes a
diff, waits for explicit approval, applies only inside a registered project mount, verifies
the result, and persists task history and rollback data.

## Architecture

- desktop/AiAgent.Desktop.sln: .NET 10 solution.
- AiAgent.Desktop: native Avalonia 12 MVVM application. It is not a WebView or launcher.
- AiAgent.Desktop.Core: Docker orchestration, safe host-path validation, mount registry,
  generated Compose override, and typed HTTP client.
- backend: Python/FastAPI service in Docker.
- ollama: Ollama server in Docker with persistent model storage.
- model-init: one-shot model pull using OLLAMA_MODEL.
- data-init: one-shot ownership migration for the persistent backend data volume.

The desktop process runs on Windows. Backend, Ollama, and model initialization run in
Docker. Backend uses http://ollama:11434; host.docker.internal is not used by the normal
Compose configuration.

## Prerequisites

- Docker Desktop with Linux containers.
- .NET 10 SDK.
- Enough disk/RAM for the selected Ollama model.

## First Docker Start

Create local configuration and choose a model:

    cd F:\aiAgent
    Copy-Item .env.example .env
    notepad .env
    docker compose up --build

OLLAMA_MODEL can be any installed/pullable Ollama model, for example:

    OLLAMA_MODEL=qwen3:8b
    # OLLAMA_MODEL=qwen2.5-coder:7b-instruct
    # OLLAMA_MODEL=qwen2.5-coder:14b

The backend starts after Ollama is healthy. model-init downloads the selected model in
parallel, so a slow download does not make backend health disappear. Inspect progress with:

    docker compose ps -a
    docker compose logs -f model-init

For detached operation:

    docker compose up -d --build
    curl.exe http://127.0.0.1:8765/health
    curl.exe http://127.0.0.1:8765/api/status
    curl.exe http://127.0.0.1:11434/api/tags

## Avalonia Desktop Start

    scripts\install_desktop_deps.ps1
    scripts\run_desktop.ps1

The app can check Docker, start/stop the Compose services, show backend/Ollama/model status,
stream an explicit model pull, add projects with the native Windows folder picker, and run
the plan/diff/approval/report workflow.

When a folder is added, the desktop app:

1. rejects drive roots, the full user profile, Windows, Program Files, and ProgramData;
2. creates a stable mount_id;
3. writes %LOCALAPPDATA%\AiAgent\compose.projects.json;
4. mounts the host folder at /projects/<mount_id>;
5. registers host_path, container_path, and mount_id with the backend;
6. uses only the validated container path for tools and commands.

The backend stores host path only as metadata. It never executes against C:\... or F:\....
Tasks and history remain bound to backend project_id, so projects cannot share runtime
roots or task history.

Set AIAGENT_HOME to the repository directory when launching a published desktop binary
outside this checkout.

## Safety

- All backend filesystem and shell actions pass through the existing safety guards.
- Container mode rejects legacy arbitrary-path project selection endpoints.
- Every proposed patch requires explicit approval before mutation.
- No automatic commit, push, or destructive cleanup is implemented.
- Rollback verifies hashes and refuses to overwrite later manual changes.

## Verification

    .venv\Scripts\python.exe -m pytest
    .venv\Scripts\python.exe -m unittest discover
    .venv\Scripts\python.exe -m ruff check .
    .venv\Scripts\python.exe -m mypy src
    dotnet restore desktop/AiAgent.Desktop.sln
    dotnet build desktop/AiAgent.Desktop.sln -c Release
    dotnet test desktop/AiAgent.Desktop.sln -c Release
    docker compose config

See docs/docker.md, docs/desktop_app.md, and docs/multi_project_workflow.md.
