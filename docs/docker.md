# Docker Runtime

The default Compose project has three services:

- backend: non-root FastAPI service on 127.0.0.1:8765;
- ollama: Ollama on 127.0.0.1:11434, with the ollama-data volume;
- model-init: one-shot pull of OLLAMA_MODEL.
- data-init: one-shot ownership fix for existing agent-data volumes before backend starts.

Start the complete environment:

    Copy-Item .env.example .env
    docker compose up --build

Detached mode:

    docker compose up -d --build
    docker compose ps -a
    docker compose logs -f model-init

The backend always uses OLLAMA_BASE_URL=http://ollama:11434 in full Docker mode.
model-init does not gate backend startup. If a pull is slow or fails, /health remains
available and the Avalonia environment panel reports downloading/failed/missing state.

The base configuration mounts AGENT_PROJECTS_ROOT at /projects for manual operation.
The desktop app additionally generates a Compose JSON override with exact bind mounts:

    F:\some-project -> /projects/project_<stable-hash>

Backend container mode accepts only registered paths matching that exact target pattern.
Application history uses agent-data; model data uses ollama-data.

On Linux, set AGENT_UID and AGENT_GID in .env to match bind-mount ownership.

Validation:

    docker compose config
    docker compose up -d --build
    docker compose ps
    curl.exe http://127.0.0.1:8765/health
    curl.exe http://127.0.0.1:8765/api/status
    curl.exe http://127.0.0.1:11434/api/tags
