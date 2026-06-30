# Architecture Patterns

These patterns help agents reason about common homelab setups.

## Tailnet-Only Remote Access

Use Tailscale, Headscale, or similar for private access. Services are not exposed publicly.

Agent checks:

- no router port forwards for private services;
- tailnet ACLs are documented;
- admin interfaces are tailnet-only or LAN-only;
- emergency local access exists.

## Outbound Privacy VPN

Use a commercial VPN or WireGuard gateway when homelab outbound traffic should not expose the home IP.

Agent checks:

- remote access VPN and outbound privacy VPN are modeled separately;
- DNS leak behavior is understood;
- routing failure behavior is safe;
- critical management access is not accidentally routed through an unreliable tunnel.

## Proxmox + NAS Split

Use Proxmox for compute and NAS for bulk storage. Keep hot databases on reliable local or replicated storage unless the NAS is designed for database workloads.

Agent checks:

- VM/container disks and media shares are separate;
- database backup path is explicit;
- NAS outage blast radius is understood;
- snapshots are not confused with offsite backups.

## Media Server + Download Stack

Common services include Jellyfin/Plex, download clients, indexers, metadata services, and storage mounts.

Agent checks:

- media paths are mounted consistently;
- containers have restart policy and health checks;
- download clients cannot write outside intended paths;
- public sharing is deliberate.

## Local Agent Runtime

The agent is a service inside the homelab.

Agent checks:

- service manager and restart policy;
- model routing;
- MCP and CLI permissions;
- log and diagnostics path;
- safe update path;
- watchdog or health check.

