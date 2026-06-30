# MCP Servers

Each directory describes one homelab MCP server. The manifests are intentionally useful before implementation: agents can inspect the tool contract, risk level, and approval behavior before calling anything.

## Manifest Rules

- Every server has `mcp.yaml`.
- Every tool has a risk level.
- `write`, `destructive`, and `credential-access` tools must set `requires_approval: true`.
- Read tools should support bounded output and redaction.
- Planning tools should produce exact proposed changes without applying them.

## Standard README Sections

Every server README should include:

- `Implemented Read-Only Tools`
- `Smoke Test`
- `Configuration`
- `Safety Contract`

Use the smoke test before connecting a client. It only asks the server for its
tool list and does not contact live infrastructure unless the server documents
that it needs local CLIs or environment variables.

## Recommended Implementation Order

1. `proxmox` read-only inventory and task status.
2. `docker` read-only stack health.
3. `diagnostics` support bundle generation through monitoring/storage/networking.
4. Approved write tools only after read-only paths are reliable.
