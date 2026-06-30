# Homelab Setup

## Purpose

Help an agent turn a user's goals into a safe homelab setup plan.

## When To Use

Use when a user is setting up Proxmox, Docker, NAS storage, monitoring, local agents, media services, or a new node.

## Workflow

1. Inventory available hardware and network context.
2. Ask for missing constraints: power, storage, backup, noise, budget, and uptime needs.
3. Produce a plan before making changes.
4. Prefer reproducible playbooks over one-off shell commands.
5. Require approval before writing config, partitioning disks, or installing services.
6. Verify the resulting service and document access URLs.

## Setup Checklist

- Inventory hardware: CPU, RAM, disks, NICs, power constraints.
- Inventory network: LAN subnet, gateway, DNS, tailnet, ingress, outbound VPN.
- Decide storage roles: hot app data, media, backups, snapshots, offsite copy.
- Decide service placement: Proxmox host, VM, LXC, Docker host, NAS, local agent runtime.
- Create read-only credentials first.
- Write `templates/inventory/homelab.inventory.example.yaml` for the user's lab.
- Apply `guardrails/policies/default-policy.yaml` before enabling write tools.

## Common Warnings

- A backup on the same physical node is not a real backup.
- Databases should not depend on flaky NAS mounts unless intentionally designed for it.
- Tailscale remote access is not the same as outbound privacy VPN.
- Public ingress should be deliberate and documented.
