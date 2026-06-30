# Example: Proxmox VM Maintenance

Goal: let an agent inspect Proxmox health and prepare a VM maintenance plan without making changes.

## Flow

1. Load `skills/safety-harness`.
2. Load `skills/infrastructure-maintenance`.
3. Enable the Proxmox MCP server in read-only mode.
4. Ask for inventory, health, and risks.
5. Approve only the exact maintenance action you want performed.

