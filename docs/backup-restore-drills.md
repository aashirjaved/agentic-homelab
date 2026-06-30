# Backup Restore Drills

Backups are only useful when they can be restored. Agents should treat backup
freshness as a signal, not proof.

Use the read-only workflow:

```bash
examples/backup-restore-drill/workflow.yaml
```

## What To Ask The Agent

```text
Use the safety harness and the backup restore drill workflow. Inspect only
read-only storage and backup state. Do not mount, copy, restore, prune, delete,
or modify anything. Identify backup freshness, failure domain, missing restore
evidence, and a proposed non-production restore test plan.
```

## Required Evidence

The agent should report:

- source dataset, share, volume, or service;
- backup target;
- whether source and target share a failure domain;
- last successful backup timestamp;
- last successful restore-test timestamp;
- restore destination for a future test;
- exact approval needed before any restore action.

## Approval Boundary

These require explicit approval:

- mounting backup media;
- copying backup data;
- restoring data;
- deleting snapshots or old backup sets;
- pruning Docker volumes;
- changing backup schedules, retention, permissions, or destinations.

For destructive cleanup, require separate destructive-action approval.
