# Rollback Safety

Before `ApplyPatchTool` writes, the application parses and validates the complete diff and
captures every target in global snapshot artifacts. The manifest records whether the file
existed, backup location, before hash, and post-apply hash.

`RollbackTool` is a high-risk mutating `BaseTool`. It never runs shell and validates every
target with the task runtime's `FileGuard`.

Rollback is refused when:

- no applied, non-rolled-back proposal exists;
- a target escapes the task project root;
- the current hash differs from the recorded post-apply hash;
- a backup is missing;
- created files would be deleted without `confirm_created_deletions=true`.

Successful rollback restores prior bytes or deletes confirmed agent-created files, marks
the snapshot/proposal rolled back, and appends an event to task history.
