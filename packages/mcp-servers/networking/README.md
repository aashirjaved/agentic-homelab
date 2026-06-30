# Networking MCP Server

MCP interface for homelab network inventory and diagnostics.

## Initial Scope

- inspect local routes, DNS, DHCP leases, and interface status
- map known hosts
- run approved diagnostics
- plan firewall or VLAN changes

## Implemented Read-Only Tools

- `inspect_interfaces`
- `inspect_dns`
- `inspect_tailnet`
- `scan_local_services`
- `plan_firewall_change`

## Smoke Test

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python3 packages/mcp-servers/networking/server.py
```

Implemented read-only tools inspect local interfaces, DNS, Tailscale status if installed, and a bounded local-only port list. It does not scan arbitrary networks or change firewall state.

## Configuration

- Tailscale inspection is used only when the `tailscale` CLI is present.
- Service scanning is local-only and bounded.
- Public exposure and firewall changes are plan-only or approval-gated.

## Safety Contract

Default mode is read-only. Firewall, routing, VLAN, DNS, and DHCP changes require approval.
