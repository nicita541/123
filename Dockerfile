FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AGENT_PROJECT_ROOT=/workspace \
    COMPLEX_AGENT_DATA_DIR=/data \
    OLLAMA_BASE_URL=http://host.docker.internal:11434

WORKDIR /app

RUN addgroup --system agent && adduser --system --ingroup agent agent

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

RUN mkdir -p /workspace /data && chown -R agent:agent /workspace /data /app

USER agent

EXPOSE 8765

CMD ["python", "-m", "complex_agent.main", "serve", "--project", "/workspace", "--host", "0.0.0.0", "--port", "8765"]
