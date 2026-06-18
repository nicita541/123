# Multi-project Workflow

The sidebar lists saved, non-archived projects ordered by `last_opened_at`. Adding a path
normalizes and deduplicates it; opening a project switches workspace browsing and its task
feed. Archiving hides the project without deleting tasks or files.

Every task stores `project_id`. Plan, proposal, approval, apply, verification, fix, report,
and rollback resolve their runtime from this persisted ID. Switching the active UI project
does not change a previously created task's sandbox, so a proposal for project A cannot be
applied in project B.

Task history is grouped by date in the UI. Opening a completed task restores messages, plan,
diff, approval state, verification output, and report without rerunning it. Repeat creates a
new child task; Continue appends a message and starts a new plan cycle in the same history.
