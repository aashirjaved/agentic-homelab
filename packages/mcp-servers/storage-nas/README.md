# Storage NAS MCP Server

MCP interface for storage health, shares, pools, snapshots, and backup readiness.

## Initial Scope

- read disk and pool health
- inspect shares and mounts
- check snapshot and backup freshness
- plan capacity changes

## Implemented Read-Only Tools

- `list_disks`
- `read_smart_health`
- `list_pools`
- `check_backup_freshness`
- `plan_share_change`

## Smoke Test

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python3 packages/mcp-servers/storage-nas/server.py
```

Implemented read-only tools list disks, mounts/filesystems, optional SMART health, and backup freshness for explicitly configured `BACKUP_PATHS`.

## Configuration

- `BACKUP_PATHS` can list comma-separated backup paths for freshness checks.
- SMART health is used only when `smartctl` is present and accessible.
- Missing storage CLIs degrade to explanatory output.

## Safety Contract

Default mode is read-only. Disk formatting, pool changes, dataset deletion, and permission changes require approval.
