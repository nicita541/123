# MVP Audit Report

## Executive summary

The project in `F:\aiAgent` is a runnable MVP, but it is not ready to treat as a stable Phase 1 baseline. Core planning, tool registry, safety checks, CLI execution, SQLite history, artifact reports, and unittest coverage exist and work for the narrow scenarios tested. The implementation is still closer to an executable scaffold than a complete coding agent.

The footprint is larger than necessary for the current behavior: there are 183 project files excluding `.agent`, `__pycache__`, and `.pyc`; `src/complex_agent` contains 136 Python files, including 47 Python files under 10 lines. This is mostly caused by many planned subsystem modules, placeholder adapters, and package `__init__.py` files.

Highest-priority findings:
- `SearchFilesTool` can expose matches from `.env` even though `ReadFileTool` blocks `.env`.
- `AgentRuntime` creates `.agent/runs.sqlite3` on initialization, so read-only commands such as `status`, `tools`, and `plan` still mutate the workspace.
- The package is not installed in the current environment, so `python -m complex_agent.main ...` fails unless `PYTHONPATH=src` is set or the package is installed editable.
- `pytest` was not run because `pytest` is not installed in the current Python environment.
- Several tools are registered but intentionally disabled or only skeletons, so `agent tools` overstates what is actually usable.

## What is implemented

- Project metadata and packaging:
  - `pyproject.toml` with package metadata, console script, and dev dependencies.
  - `README.md`, `AGENTS.md`, config files, docs, examples, and scripts.
- Core runtime:
  - `Task`, `AgentState`, `Step`, `Observation`, `Result`, modes, statuses, and errors.
  - `AgentRuntime` and `AgentLoop` wiring planner, executor, tools, safety, verifier, storage, and reports.
- Planning:
  - Deterministic MVP planner.
  - Plan and plan-step models.
  - Basic validation.
  - Basic replanner class, though not integrated into a real failure loop.
- Tools:
  - `ToolRegistry` and `BaseTool`.
  - Working tools for project scan, read file, list files, search files, diff, apply patch, shell, git status/diff/branch, dependency scan, diagnostics, build, lint, and test runner wrappers.
- Safety:
  - File guard for sensitive paths and root escape checks.
  - Command guard with allowlist, blocked fragments, and shell-operator rejection.
  - Approval gate and secret redaction.
- Execution:
  - Executor runs plan steps through `ToolRegistry`.
  - Mutating tools require approval.
  - Observations and changed files are recorded.
- Storage and artifacts:
  - SQLite run history exists.
  - Markdown report artifacts are created under `.agent/artifacts`.
- CLI:
  - `plan`, `review`, `run`, `audit`, `tools`, `status`, `history`, and `config` are implemented through argparse.
- Tests:
  - 14 unittest tests cover basic CLI, planner, executor, safety, filesystem tools, shell blocking, context, memory, and verifier behavior.

## What works

Verified commands:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover
python -m complex_agent.main --project . status
python -m complex_agent.main --project . tools
python -m complex_agent.main --project . plan "Audit this project"
python -m complex_agent.main --project . audit "Audit this project"
```

Observed results:
- `unittest discover` passed: 14 tests.
- `status` reports the project root and 18 registered tools.
- `tools` lists registered tools.
- `plan "Audit this project"` creates a conservative plan.
- `audit "Audit this project"` completed and created a report artifact.
- SQLite exists at `.agent/runs.sqlite3`; audit runs and observations are persisted.
- Artifacts exist under `.agent/artifacts`.
- `ReadFileTool` blocks `.env`.
- `CommandGuard` blocks `git reset --hard`.
- `ApprovalGate` prevents `apply_patch` mutation in Review Mode when `auto_approve=False`.
- `ToolRegistry` does invoke real tool implementations during audit.

## What is only skeleton/stub

The following are explicit placeholders or not implemented in MVP:
- `api/server.py`: FastAPI server is not implemented.
- `execution/rollback_manager.py`: rollback is not implemented.
- `llm/openai_provider.py`: OpenAI provider is a placeholder.
- `llm/provider.py`: abstract interface only.
- `memory/memory_store.py`: abstract interface only.
- `memory/long_term_memory.py`: placeholder.
- `memory/vector_memory.py`: returns no results.
- `subagents/*`: placeholder.
- `skills/*`: placeholder.
- `tools/mcp/*`: placeholder.
- `tools/web/search_tool.py` and `tools/web/fetch_url_tool.py`: not implemented.
- `tools/code/symbol_index_tool.py`: placeholder.
- `tools/code/format_tool.py`: disabled.
- `tools/git/git_commit_tool.py`: disabled.
- `review/final_report_builder.py`: usable final report builder exists, but `FinalReportTool` is only a simple placeholder step.
- `verification/build_verifier.py`, `test_verifier.py`, and `lint_verifier.py`: thin aliases to tools, not real verifier classes.

These skeletons are acceptable only if they are clearly documented as future expansion points. They should not be presented as completed features.

## Risks

- The MVP can look more complete than it is because many future modules already exist.
- Registered-but-disabled tools make the CLI tool list misleading.
- The deterministic planner does not actually understand code changes; it only creates conservative scan/status/diff/final steps.
- No real LLM-backed structured planning exists yet.
- Replanning is not integrated into the runtime loop.
- Rollback is declared but not implemented.
- The current patch applier is intentionally small and should not be trusted for complex diffs.
- No packaging/install validation has been completed because dev dependencies are not installed.

## Architecture issues

- The project is over-expanded for the current behavior. `src/complex_agent` has 136 Python files; many are very small placeholder modules.
- `AgentRuntime` performs storage initialization immediately. This creates `.agent/runs.sqlite3` even for commands that should be read-only.
- CLI commands instantiate the full runtime even when they only need static metadata, causing avoidable side effects.
- The event bus and audit log exist but are only lightly used.
- `Verifier` is too shallow: it checks observation success but does not validate changed files, diffs, forbidden file changes, build/test status, or task completion semantics.
- `FinalReportTool` and `FinalReportBuilder` overlap conceptually.
- The current planner does not use `TaskDecomposer`, `Replanner`, LLM structured output, or context relevance beyond initial request metadata.

## Security issues

- Critical: `SearchFilesTool` can search `.env` and return a matching line. A direct test showed:
  - `ReadFileTool` for `.env`: blocked.
  - `SearchFilesTool` for a secret marker: succeeded and returned the `.env` path plus redacted content.
- `SearchFilesTool` uses `rg` or Python fallback but does not consistently apply `FileGuard` to every search result before returning it.
- Secret redaction is regex-based and incomplete; it should not be the only defense.
- `CommandGuard` uses simple string prefix logic and `command.split()`, not robust shell parsing.
- `ShellTool` blocks common shell operators, but command policy needs more tests for Windows PowerShell edge cases.
- `ApplyPatchTool` writes files directly after executor approval; direct tool calls can still mutate if called with a context, so callers must never bypass executor/safety.
- `.agent` artifacts may contain command outputs; retention and redaction policy are not fully enforced.

## Test issues

Existing tests cover:
- basic planner validity;
- basic CLI command return codes;
- `.env` direct read blocking;
- dangerous command blocking;
- shell unallowlisted command rejection;
- patch application success;
- approval rejection for mutation;
- audit run without git repository;
- simple memory/context/verifier behavior.

Missing tests:
- `SearchFilesTool` must not return `.env` or forbidden-path matches.
- `SearchFilesTool` must not leak secret paths or secret keys.
- CLI commands that should be read-only should not create `.agent`.
- `agent review` must not mutate files without approval.
- `agent run --yes` should apply an approved patch in a controlled fixture.
- SQLite history should avoid duplicated observations on repeated saves of the same state.
- Artifact redaction should be tested.
- CommandGuard needs Windows-specific destructive command tests.
- Patch applier needs tests for create-file, context mismatch, forbidden path, malformed diff, and multi-hunk behavior.
- ToolRegistry should reject unknown tools and missing input schemas.
- Verifier should test changed-file limits, forbidden changed files, failed test/build observations, and final-report content.
- CLI should be tested after editable install, not only with `PYTHONPATH=src`.

Why pytest was not run:
- `python -m pytest --version` failed with `No module named pytest`.
- The current environment has Python 3.12.10 but does not have dev dependencies installed.

What is needed for pytest:

```powershell
cd F:\aiAgent
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest
```

## Extra files / project bloat

Current counts:
- All files including generated state: 341.
- Candidate project files excluding `.agent`, `__pycache__`, and `.pyc`: 183.
- Generated files observed:
  - `.agent`: 3 files.
  - `__pycache__`: 156 files.
- Candidate project files by top-level directory:
  - `src`: 136.
  - `tests`: 20.
  - `docs`: 8.
  - `config`: 6.
  - `examples`: 4.
  - `scripts`: 4.
  - root metadata/docs: 5.

Assessment:
- The 183 candidate files are explainable from the planned architecture, but too many are not doing useful MVP work yet.
- The strongest bloat sources are future-facing modules: `api`, `subagents`, `skills`, `mcp`, `web`, vector/long-term memory, and several thin verifier wrappers.
- Many `__init__.py` files are required for package/test discovery, but they inflate the raw count.
- `.agent` and `__pycache__` are generated state, not source. They should remain ignored and can be cleaned when needed.

Recommended cleanup before Phase 2:
- Keep placeholders only where they document a near-term extension boundary.
- Remove or unregister disabled tools from the default registry until they are usable.
- Consider moving future-only API/subagent/MCP/web placeholders to docs until implementation starts.
- Do not add new modules until current modules have meaningful tests and behavior.

## What to fix before Phase 2

1. Fix `SearchFilesTool` so it applies `FileGuard` to all candidate files and never returns forbidden paths or secret matches.
2. Stop read-only CLI commands from creating `.agent` state.
3. Decide whether disabled tools should be registered. Prefer not listing tools that cannot run.
4. Install dev dependencies and run pytest.
5. Add the missing critical tests listed above.
6. Make verifier stronger: check forbidden changed files, diff relevance, test/build failures, and final status.
7. Separate report-building from the `final_report` tool placeholder.
8. Improve command parsing and Windows command-deny coverage.
9. Document which modules are MVP-complete and which are intentionally future-only.
10. Consider reducing skeleton modules before adding Phase 2 features.

## Recommended next task order

1. Set up the dev environment and run `pytest` plus `unittest`.
2. Add failing tests for `.env` leakage through `SearchFilesTool`.
3. Fix `SearchFilesTool` safety filtering.
4. Add tests proving read-only CLI commands do not create runtime state.
5. Refactor `AgentRuntime` storage initialization to be lazy or mode-specific.
6. Unregister or hide disabled tools from default `agent tools`.
7. Strengthen verifier around changed files, forbidden paths, and failed commands.
8. Add tests for approval-gated CLI mutation behavior.
9. Re-run audit and update this report.

