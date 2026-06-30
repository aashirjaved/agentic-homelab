# VM Management MCP Server

Cross-platform MCP interface for VM inventory and lifecycle planning.

## Initial Scope

- normalize VM inventory across Proxmox, libvirt, and local hypervisors
- inspect VM resources
- plan resize, snapshot, backup, and migration operations

## Implemented Read-Only Tools

- `list_vms`
- `inspect_vm`
- `plan_snapshot`

## Smoke Test

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python3 packages/mcp-servers/vm-management/server.py
```

Implemented read-only tools list VM/service placement hints from JSON inventory and inspect local libvirt VMs when `virsh` is available. Snapshot creation, resize, and deletion are intentionally not implemented.

## Configuration

- `AGENTIC_HOMELAB_INVENTORY` can point at a JSON inventory for placement hints.
- `virsh` is used only when present.
- Provider-specific writes are intentionally omitted from the reference server.

## Safety Contract

Default mode is read-only. Snapshot deletion, disk resize, migration, and power operations require approval.
