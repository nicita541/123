# Persistence Architecture

## Location

`AppPaths` resolves `%LOCALAPPDATA%\ComplexAgent` on Windows and `~\.complex_agent`
otherwise. `COMPLEX_AGENT_DATA_DIR` is an explicit override for tests and Docker.

```text
ComplexAgent/
  app.sqlite3
  artifacts/
    reports/
    snapshots/
  logs/
  cache/
  config.yaml
```

Projects are not modified to store application history. Existing `.agent` directories are
left untouched for compatibility but are not imported automatically.

## Database

`AppStore` enables foreign keys, WAL, a busy timeout, and uses an immediate transaction for
mutations. Schema version 1 contains users, projects, tasks, messages, plans, proposals,
approvals, runs, snapshots, events, settings, and migration records.

Task plans and changed-file lists use JSON columns. Reports and verification output are
stored in SQLite for restart-safe API reads; report files and snapshot bytes also live in
global artifacts. IDs are opaque strings and timestamps are UTC ISO-8601 values.

The default local identity is `local-user` with role `owner`. Team-facing ownership and
visibility columns are populated but do not grant network access or authorization.
