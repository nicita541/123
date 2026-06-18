# Architecture

    Avalonia Desktop (Windows)
      |-- DockerComposeService --> Docker Compose
      |                             |-- backend (FastAPI)
      |                             |-- ollama
      |                             +-- model-init
      |                             +-- data-init
      +-- AgentApiClient ---------> backend HTTP API
                                      |-- SessionStore / AgentRuntime
                                      |-- SafetyPolicy / FileGuard / CommandGuard
                                      |-- planning / execution / verification / review
                                      +-- SQLite application history

The desktop is split into native UI and AiAgent.Desktop.Core. Core owns deterministic mount
IDs, host path guards, settings, structured Compose override generation, direct process
invocation, and typed HTTP DTOs. It has no Avalonia dependency.

The backend remains provider-neutral at the core boundary. Ollama integration is selected
through configuration. LLM output is a proposal and must pass schema validation, safety
checks, and approval before a mutating tool runs.

Container mode adds a second trust boundary: a Windows host path is never a backend runtime
path. The backend accepts a project only when its declared container path exactly matches a
mounted /projects/<mount-id> directory.
