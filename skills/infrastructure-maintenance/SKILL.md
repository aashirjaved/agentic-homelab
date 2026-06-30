# Infrastructure Maintenance

## Purpose

Help an agent perform routine homelab maintenance safely.

## When To Use

Use for updates, disk checks, failed containers, VM health, backup verification, certificate renewals, monitoring alerts, and capacity reviews.

## Workflow

1. Start in read-only mode.
2. Gather inventory, health, logs, versions, and recent changes.
3. Explain the issue and the proposed maintenance window.
4. Create a rollback plan for risky changes.
5. Ask for approval before writes or restarts.
6. Verify after changes and record what changed.

## Maintenance Checklist

- Confirm the current inventory and target node.
- Check recent failed jobs, alerts, and logs.
- Check disk pressure before updates, snapshots, or backups.
- Check whether services are exposed publicly, tailnet-only, or LAN-only.
- Prefer one service or node at a time.
- Produce a rollback plan for every write.
- Leave a maintenance note with timestamp, action, verifier, and residual risk.

## Verification Examples

- Proxmox task finished with `OK`.
- Docker health status is `healthy`.
- Service responds on health endpoint.
- Logs stop showing the target error.
- SMART status remains passing.
- Backup restore test succeeds.
