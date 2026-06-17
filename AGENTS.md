# AGENTS.md

## Project Layout

- `src/complex_agent/core`: task state, modes, observations, results and the agent loop.
- `src/complex_agent/planning`: plan creation, validation and replanning.
- `src/complex_agent/execution`: approved step execution.
- `src/complex_agent/tools`: all filesystem, shell, git, code and project tools.
- `src/complex_agent/safety`: file, command, approval and secret guards.
- `src/complex_agent/verification`: build/test/diff/result checks.
- `src/complex_agent/review`: diff review, risk analysis and final reports.
- `src/complex_agent/storage`: SQLite run history and artifact storage.
- `src/complex_agent/ui`: CLI, rendering and approvals.

## Commands

```powershell
python -m unittest discover
python -m pytest
ruff check .
mypy src
```

## Safety Rules

- Do not read or log `.env`, private keys, credentials or token files.
- Do not mutate files outside approved tools.
- Do not call shell commands directly from core, planning or review code.
- Do not bypass `SafetyPolicy`, `FileGuard`, `CommandGuard` or `ApprovalGate`.
- Do not couple core logic to a specific LLM provider.
- Do not add git push, auto-commit or destructive cleanup behavior in MVP.

## Adding Tools

New tools must implement `BaseTool`, define typed input expectations, declare `risk_level` and `mutates`, add safety coverage, and include tests for allowed and denied calls.

## Definition of Done

Changes are ready when tests pass, safety behavior is covered, CLI behavior is documented, and reports clearly state actions, checks and residual risks.

