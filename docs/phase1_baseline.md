# Phase 1 Stable Baseline

## What Is Included

Phase 1 is the stabilized MVP baseline for the current CLI-first coding agent scope:

- deterministic planning for `plan`, `review`, `run`, and `audit` flows;
- core task/state/result models and agent loop wiring;
- safety-gated tool execution through `ToolRegistry`;
- file, command, approval, and secret guards;
- safe project scan, read, search, diff, patch, shell, git, lint, build, and test-runner tool wrappers;
- SQLite run history and markdown report artifacts for executing commands;
- CLI commands for `plan`, `review`, `run`, `audit`, `tools`, `status`, `history`, and `config`;
- unit tests and pytest coverage for critical MVP safety and runtime behavior.

## Validation Commands Passed

Run from `F:\aiAgent`:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m unittest discover
.venv\Scripts\python.exe -m compileall -q src tests
```

Expected current result:

- `pytest`: 39 tests passed.
- `unittest`: 39 tests passed.
- `compileall`: passed.

## Remaining Limits

- The planner is deterministic and conservative; it is not an LLM-backed code-change planner.
- The verifier is stricter than the initial MVP, but it is not a full semantic diff reviewer.
- The patch applier is intentionally small and should not be trusted for complex diffs.
- Rollback is not implemented.
- API, MCP, subagents, web UI, vector memory, long-term memory, and real LLM provider execution are not part of Phase 1.
- SQLite history and artifacts are functional but intentionally simple.

## Source Directories

These directories/files are source and documentation for the baseline:

- `src/complex_agent/`
- `tests/`
- `config/`
- `docs/`
- `examples/`
- `scripts/`
- `README.md`
- `AGENTS.md`
- `pyproject.toml`
- `.env.example`
- `.gitignore`

## Generated Directories

These are generated or local environment directories and should not be committed:

- `.agent/`
- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `*.pyc`
- build/package output such as `build/`, `dist/`, and `*.egg-info/`

## MVP-Ready Modules

These modules are considered ready for the Phase 1 baseline:

- `core`
- `planning`
- `execution`
- `tools` for enabled MVP tools
- `safety`
- `context`
- `memory` short-term memory
- `storage`
- `events`
- `verification` baseline verifier
- `review` final report builder
- `ui` CLI
- `utils`

## Future Placeholders

These modules are intentionally present as extension boundaries but are not Phase 1 features:

- `api`
- `subagents`
- `skills`
- `tools/mcp`
- `tools/web`
- `memory/vector_memory.py`
- `memory/long_term_memory.py`
- `execution/rollback_manager.py`
- `llm/openai_provider.py`

Disabled or internal tools must not be presented as fully available MVP capabilities.

## Rules Before Phase 2

- Do not start Phase 2 without a separate plan.
- Do not add API, MCP, subagents, rollback, web UI, vector memory, long-term memory, or LLM integration as incidental work.
- Keep changes small and tied to a stated Phase 2 goal.
- Run the baseline validation commands before and after Phase 2 changes.
- Keep read-only CLI commands free of runtime-state side effects.
- Preserve safety invariants for forbidden files, secret redaction, approval-gated mutation, and blocked destructive commands.
