# MVP Stabilization Report

## Executive Summary

The MVP stabilization pass is complete. The work stayed within the audit findings and did not add Phase 2 capabilities such as API, MCP, subagents, rollback, web UI, vector memory, long-term memory, or LLM integration.

The MVP is now a stable Phase 1 baseline for its current scope: conservative planning, safety-gated tools, CLI execution, SQLite run history, artifact reports, and test coverage for the critical audit findings.

## Fixed Findings

- `SearchFilesTool` no longer uses raw project-wide `rg` output. It searches only files that pass `FileGuard.validate_read`.
- Search results now skip secret-bearing lines when `SecretsGuard.redact(line)` would modify the line.
- Search results no longer expose forbidden paths such as `.env`, `secret/*`, `token/*`, private keys, or other denied files.
- `AgentRuntime` now initializes SQLite and artifact storage lazily. Read-only commands do not create `.agent`, `runs.sqlite3`, or artifacts.
- `agent tools` now shows tool status instead of presenting disabled/internal tools as fully available.
- `git_commit` is marked `disabled`; `final_report` is marked `internal`.
- `Verifier` now catches failed observations, failed shell/build/test/lint observations, forbidden changed files, unapproved changed-file records, and final reports that hide existing errors.
- `Executor` annotates approved mutating tool observations with `mutation_approved` metadata.
- `CommandGuard` now explicitly blocks additional Windows/PowerShell destructive or download-execute commands.
- Dev dependencies were installed in `.venv`, and `pytest` now runs.

## Tests Added

Search safety:
- `search_files` does not return `.env`.
- `search_files` does not return secret markers or secret values.
- `search_files` does not return forbidden paths.
- `read_file` and `search_files` enforce the same file guard policy.

CLI/storage behavior:
- `status`, `tools`, `plan`, and `config` do not create `.agent`.
- `audit` still creates SQLite run history and markdown artifacts.
- disabled/internal tools are not shown as fully available.

Verifier behavior:
- failed observations without explicit errors fail verification.
- failed `shell`, `build`, and `test_runner` observations fail verification.
- forbidden changed files fail verification.
- changed files without approved mutation metadata fail verification.
- final reports that hide existing errors fail verification.

Command safety:
- `del /s`
- `rmdir /s`
- `Remove-Item -Recurse`
- `Invoke-Expression`
- `iwr ... | iex`
- `curl ... | powershell`
- `git reset --hard`
- `git clean -fdx`

## Commands Run

Focused tests after patch blocks:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.tools.test_filesystem_tools
$env:PYTHONPATH='src'; python -m unittest tests.cli.test_cli
$env:PYTHONPATH='src'; python -m unittest tests.verification.test_verifier
$env:PYTHONPATH='src'; python -m unittest tests.safety.test_safety_policy
```

Results: all focused tests passed.

Pre-venv validation:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover
$env:PYTHONPATH='src'; python -m compileall -q src tests
```

Results: `27` unittest tests passed; compileall passed.

Dev environment setup:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Result: editable install and dev dependencies completed successfully.

Final validation:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m unittest discover
.venv\Scripts\python.exe -m compileall -q src tests
.venv\Scripts\python.exe -m complex_agent.main --project . status
.venv\Scripts\python.exe -m complex_agent.main --project . tools
.venv\Scripts\python.exe -m complex_agent.main --project . plan "Audit this project"
.venv\Scripts\python.exe -m complex_agent.main --project . audit "Audit this project"
```

Results:
- `pytest`: `27 passed`.
- `unittest`: `27 tests OK`.
- `compileall`: passed.
- `status`: passed; reports `16` enabled tools.
- `tools`: passed; displays `enabled`, `disabled`, and `internal` statuses.
- `plan`: passed.
- `audit`: passed and created a report artifact.

## Remaining Issues

- The MVP still contains future-facing skeleton modules for API, MCP, subagents, web tools, vector memory, long-term memory, rollback, and real LLM providers. These remain intentionally unimplemented.
- The planner is still deterministic and conservative; it does not perform LLM-backed code-change planning.
- The verifier is stricter but still not a full semantic diff reviewer.
- The patch applier remains intentionally small and should not be trusted for complex diffs.
- SQLite history can still be improved in later work, especially around duplicate observation persistence on repeated saves.
- Generated state exists under `.agent`, `.venv`, and `__pycache__`; these are not source files.

## Baseline Assessment

The MVP can now be considered a stable Phase 1 baseline for the current feature set. The critical audit problems were addressed, dev dependencies install successfully, and the project passes `pytest`, `unittest`, `compileall`, and installed-package CLI checks.

It should not be treated as a complete coding agent yet. Phase 2 should start only after agreeing on the next narrow capability, with no broad architecture expansion.

