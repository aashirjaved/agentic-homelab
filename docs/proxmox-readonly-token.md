# Proxmox Read-Only Token

Use API tokens instead of root passwords when agents inspect Proxmox.

## Goal

Create one token for read-only discovery. Keep write or admin tokens separate and approval-gated.

## Suggested Permissions

Start with the least privilege that allows inventory:

- `Sys.Audit` for node and cluster status
- `VM.Audit` for VM/container inventory and config
- `Datastore.Audit` for storage visibility

Apply at the narrowest path that fits your lab. For a single-node hobby lab this is often `/`, but narrower paths are better when practical.

## Environment Variables

```bash
export PROXMOX_API_URL="https://pve.example.internal:8006"
export PROXMOX_API_TOKEN_ID="user@realm!agent-readonly"
export PROXMOX_API_TOKEN_SECRET="<secret from password manager>"
export PROXMOX_VERIFY_TLS="true"
```

Do not commit these values. Use your agent's secret store, OS keychain, shell profile outside the repo, or a local `.env` ignored by git.

## First Agent Task

```text
Use the Proxmox MCP server in read-only mode. Run list_nodes, list_guests, list_storage, and list_recent_tasks. Summarize health, risks, and missing context. Do not make changes.
```

## Red Flags

- Token belongs to `root@pam`.
- Token can modify VM lifecycle.
- Token secret appears in chat, logs, shell history, or git.
- TLS verification is disabled permanently instead of only during setup.

