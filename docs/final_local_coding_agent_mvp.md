# Final Local Coding Agent MVP

## Scope

This MVP is a local coding-agent workspace with a safe end-to-end edit loop:

```text
task -> plan -> proposed diff -> approval -> ApplyPatchTool -> self-test -> final report
```

It keeps the Phase 1 safety model and the MVP 2/3 local FastAPI app. It does not add
cloud execution, direct shell endpoints, direct write endpoints, subagents, MCP,
rollback, vector memory, or long-term memory.

## Launch

Run from `F:\aiAgent`:

```powershell
.venv\Scripts\python.exe -m complex_agent.main serve --project . --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

The default bind address is local-only: `127.0.0.1`.

## Calculator Demo

The calculator demo is deterministic and does not require an LLM or Ollama.

Example task:

```text
Сделай консольный калькулятор на Python с операциями +, -, *, /
```

Expected flow:

1. The UI/API creates a plan.
2. The deterministic calculator skill proposes a unified diff for `calculator.py`.
3. The app shows the diff and waits for approval.
4. After approval, `ApplyPatchTool` applies the patch.
5. The runtime executes `python calculator.py --self-test`.
6. The final report explains changed files, verification, and how to run the calculator.

## Ollama Local Models

Ollama is optional. It is used only for tasks that deterministic skills do not cover.
If Ollama is unavailable, the app shows a clear fallback message and does not create
files for unknown tasks.

Default settings live in `config/models.yaml`:

```yaml
llm:
  provider: ollama
  fallback_provider: deterministic
  ollama:
    base_url: "http://127.0.0.1:11434"
    model: "qwen2.5-coder:7b"
    timeout_seconds: 60
```

Environment overrides:

```powershell
set OLLAMA_BASE_URL=http://127.0.0.1:11434
set OLLAMA_MODEL=qwen2.5-coder:7b
```

Install and pull a model:

```powershell
ollama pull qwen2.5-coder:7b
```

Ollama may generate:

- structured plans;
- proposed unified diffs.

Ollama may not:

- read files directly;
- write files directly;
- execute shell commands;
- bypass approval;
- bypass `PatchGenerator`, `FileGuard`, `SecretsGuard`, or `ApplyPatchTool`.

## Status Visibility

CLI:

```powershell
.venv\Scripts\python.exe -m complex_agent.main --project . status
```

API:

```text
GET /api/status
```

Both expose:

- LLM provider;
- Ollama base URL;
- Ollama model;
- Ollama reachable status.

The UI shows the same information in the right-side `Среда` card.

## Safety Guarantees

- No direct frontend endpoint exists for arbitrary shell, arbitrary git commands,
  file writes, or raw patch application.
- Read-only status and planning endpoints do not create `.agent`, SQLite history,
  or artifacts.
- Mutating execution goes through `AgentRuntime`, `ToolRegistry`, `SafetyPolicy`,
  `ApprovalGate`, and `ApplyPatchTool`.
- Forbidden paths such as `.env`, `.agent`, `.venv`, secret/token/private-key files
  are not exposed through file/search previews.
- Secret-like output is redacted before it reaches API/UI responses.

## Limits

- Sessions are in-memory and are lost on backend restart.
- There is no authentication; the server is intended for local use only.
- The UI is static HTML/CSS/JS with no frontend build pipeline.
- Unknown LLM tasks require a reachable local Ollama model.
- Rollback, subagents, MCP, API hardening, cloud execution, vector memory, and
  long-term memory remain outside this MVP.
