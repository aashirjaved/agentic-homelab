# Proxmox MCP Server

MCP interface for Proxmox VE inventory, health checks, VM lifecycle planning, and approved VM operations.

## Initial Scope

- list nodes, VMs, containers, storage, and networks
- read node health and cluster status
- inspect VM configuration
- prepare migration, backup, and resize plans
- execute approved lifecycle actions in a future milestone

## Implemented Read-Only Tools

- `list_nodes`
- `list_guests`
- `get_guest_config`
- `list_storage`
- `list_recent_tasks`

## Smoke Test

The reference server is intentionally read-only and safe to run without credentials:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python3 packages/mcp-servers/proxmox/server.py
```

It can list Proxmox nodes from a JSON inventory referenced by `AGENTIC_HOMELAB_INVENTORY`. When API environment variables are present, it also performs read-only Proxmox API calls.

## Read-Only API Configuration

Create a Proxmox API token with read-only privileges, then configure:

```bash
export PROXMOX_API_URL="https://pve.example.internal:8006"
export PROXMOX_API_TOKEN_ID="user@realm!token-name"
export PROXMOX_API_TOKEN_SECRET="<from your secret store>"
export PROXMOX_VERIFY_TLS="true"
```

For a self-signed lab certificate, either install your CA locally or set `PROXMOX_VERIFY_TLS=false` for testing.

Shell exports only work when you launch the server from that shell. Desktop
MCP clients (Claude Desktop and similar) start servers with their own
environment, so bake the credentials into the generated config instead:

```bash
python3 scripts/generate_mcp_config.py \
  --servers proxmox \
  --env PROXMOX_API_URL="https://pve.example.internal:8006" \
  --env PROXMOX_API_TOKEN_ID="user@realm!token-name" \
  --env PROXMOX_API_TOKEN_SECRET="<from your secret store>" \
  --output generated/mcp-config.json
```

Implemented read-only tools:

- `list_nodes`
- `list_guests`
- `get_guest_config`
- `list_storage`
- `list_recent_tasks`

Write, power, and delete tools are intentionally not implemented in the reference server.

## Configuration

- `AGENTIC_HOMELAB_INVENTORY` can point at a JSON inventory for offline discovery.
- Proxmox API mode requires the read-only token variables below.
- Secret values should come from your shell, password manager, or runtime secret store.

## Safety Contract

Default mode is read-only. Power operations, deletion, disk resize, network changes, and migration require explicit approval.
