FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AGENT_PROJECTS_ROOT=/projects \
    AGENT_PROJECT_ROOT=/projects/docker_workspace \
    COMPLEX_AGENT_DATA_DIR=/data \
    OLLAMA_BASE_URL=http://ollama:11434

ARG AGENT_UID=1000
ARG AGENT_GID=1000

WORKDIR /app

RUN addgroup --gid "${AGENT_GID}" agent \
    && adduser --disabled-password --gecos "" --uid "${AGENT_UID}" --gid "${AGENT_GID}" agent

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

RUN mkdir -p /projects/docker_workspace /data \
    && chown -R agent:agent /projects /data /app

USER agent

EXPOSE 8765

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=2)"]

CMD ["python", "-m", "complex_agent.main", "serve", "--project", "/projects/docker_workspace", "--host", "0.0.0.0", "--port", "8765"]
