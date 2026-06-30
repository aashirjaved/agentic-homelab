# Example: Backup Restore Drill

Goal: let an agent check whether backups look restorable before any risky
maintenance.

## Flow

1. Inspect backup freshness and storage health.
2. Identify source, backup target, and failure domain.
3. Check whether a restore test exists and when it last passed.
4. Produce a test-restore plan that does not overwrite production data.
5. Require explicit approval before mounting, copying, deleting, pruning, or
   restoring anything.

This workflow is intentionally read-only. A backup that exists but has never
been restored is an assumption, not evidence.
