# Inventory Templates

Inventories give agents a safe map of your homelab without storing secrets.

## Templates

- `homelab.inventory.example.yaml` - minimal starter.
- `homelab.inventory.example.json` - JSON version for dependency-light MCP reference servers.
- `single-node-docker-media.yaml` - one host running Docker media services.
- `proxmox-nas-split.yaml` - Proxmox compute with separate NAS storage.
- `local-agent-runtime.yaml` - OpenClaw/Hermes/local-agent host.

## Rules

- Use `credential_ref`, not secret values.
- Prefer documentation of exposure: `internal-only`, `lan-only`, `tailnet-only`, or `public`.
- Mark backup uncertainty honestly.
- Separate hot database storage from bulk media storage when possible.
- Keep public ingress explicit.

## First Agent Prompt

```text
Read this inventory and the default guardrail policy. Identify missing context, single points of failure, public exposure, backup gaps, and which checks can be done read-only. Do not make changes.
```

