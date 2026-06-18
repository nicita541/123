# Docker

Run a selected workspace through the guarded PowerShell wrapper:

```powershell
scripts\docker_run.ps1 -Workspace F:\1
```

The script resolves the path and rejects a drive root, the complete home directory, Windows,
and Program Files. The workspace is mounted at `/workspace`; global state uses the named
`agent-data` volume at `/data`. The image runs as the non-root `agent` user.

Manual configuration:

```powershell
$env:AGENT_WORKSPACE = "F:\1"
$env:OLLAMA_BASE_URL = "http://host.docker.internal:11434"
$env:OLLAMA_MODEL = "qwen2.5-coder:7b-instruct"
docker compose up --build agent-app
```

Without `AGENT_WORKSPACE`, Compose uses the ignored `examples/docker_workspace` directory.
`host.docker.internal` is mapped through `host-gateway` for Linux compatibility.

Container Ollama is optional:

```powershell
docker compose --profile ollama up --build
```

Validate with `docker compose config`, then check `/health`, `/api/status`, and that project
paths reported by the container remain under `/workspace`.
