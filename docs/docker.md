# Docker

The Docker setup runs the local agent backend and static UI in a Python 3.12 container.
The container must receive one explicitly selected workspace mounted at `/workspace`.

## Safety model

- The container sees only the mounted workspace volume and application image files.
- File tools and `ApplyPatchTool` use `/workspace` as the selected project root.
- `ShellTool` runs with `cwd=/workspace`.
- `.env`, `.agent`, `.venv`, `.git`, `__pycache__`, secret/token/private-key paths remain blocked.
- Destructive shell commands, auto-commit, and auto-push remain disabled.
- Do not mount a whole drive or home directory. Mount only the project that the agent may change.

## Build

```powershell
cd F:\aiAgent
scripts\docker_build.ps1
```

Equivalent command:

```powershell
docker build -t complex-ai-agent:local .
```

## Run with host Ollama

Docker Desktop exposes the Windows host as `host.docker.internal`.

```powershell
cd F:\aiAgent
scripts\docker_run.ps1 -Workspace F:\1 -OllamaBaseUrl http://host.docker.internal:11434 -OllamaModel qwen3-coder:30b
```

Equivalent compose setup:

```powershell
$env:AGENT_WORKSPACE = "F:\1"
$env:OLLAMA_BASE_URL = "http://host.docker.internal:11434"
$env:OLLAMA_MODEL = "qwen3-coder:30b"
docker compose up --build agent-app
```

Open:

```text
http://127.0.0.1:8765
```

## Optional Ollama container

The compose file includes an optional `ollama` profile:

```powershell
$env:AGENT_WORKSPACE = "F:\1"
$env:OLLAMA_BASE_URL = "http://ollama:11434"
docker compose --profile ollama up --build
```

Models are not downloaded automatically. Pull a model into the Ollama service separately:

```powershell
docker compose exec ollama ollama pull qwen2.5-coder:7b-instruct
```

For a host Ollama installation:

```powershell
ollama pull qwen2.5-coder:7b-instruct
```

## Environment variables

- `AGENT_WORKSPACE`: host folder mounted to `/workspace`.
- `AGENT_PROJECT_ROOT`: fixed to `/workspace` inside the container.
- `OLLAMA_BASE_URL`: host Ollama or compose Ollama endpoint.
- `OLLAMA_MODEL`: preferred local model; the provider selects the best available model if missing.

## Desktop mode and Docker

Desktop mode normally starts its own local FastAPI backend:

```powershell
python -m complex_agent.main desktop --project F:\1
```

Docker mode is a separate browser-server deployment. The MVP desktop launcher does not
embed or control the Docker container; both modes use the same static UI and API contracts.
