# Example: Diagnostics Bundle

Goal: let an agent collect safe, redacted context before proposing any homelab maintenance.

## Required Skills

- `safety-harness`
- `infrastructure-maintenance`

## Useful MCP Servers

- `networking`
- `storage-nas`
- `monitoring`
- `docker`
- `proxmox`

## Flow

1. Read inventory and policy.
2. Inspect local interfaces, DNS, tailnet status, and local service ports.
3. Inspect disks, mounts, pools, and configured backup freshness.
4. Inspect host metrics and bounded service logs.
5. Inspect Docker and Proxmox state if configured.
6. Summarize findings, missing context, and risk.
7. Propose the next read-only check or request approval for exactly one write.

## Local Generator

Create a safe bundle without command output:

```bash
python3 scripts/create_diagnostics_bundle.py --inventory templates/inventory/homelab.inventory.example.yaml
```

Create a bundle with bounded read-only local command output:

```bash
python3 scripts/create_diagnostics_bundle.py --inventory templates/inventory/homelab.inventory.example.yaml --include-commands
```

Generated bundles go under `diagnostics/`, which is ignored by git.

## Prompt

```text
Use the safety harness. Build a diagnostics bundle for my homelab using read-only tools only. Do not print secrets. Separate observed facts from guesses. End with the safest next check and any approval needed.
```
