# Threat Model

## Assets

- Homelab nodes and hypervisors
- NAS data and backups
- Credentials and tokens
- Private network topology
- Agent memory and logs
- Media libraries and personal files
- Local model and remote model traffic

## Trust Boundaries

- Human user
- Local agent runtime
- MCP server process
- Homelab node API
- SSH shell
- Remote model provider
- Tailnet or VPN
- Public internet ingress

## Primary Risks

### Over-Broad Credentials

An agent using root or admin credentials can cause more damage than intended.

Mitigations:

- use read-only tokens first;
- keep write credentials separate;
- require approval for credential access;
- log credential reference names, not secret values.

### Unverified Automation

An agent may believe it fixed something when it only changed state or masked symptoms.

Mitigations:

- define verifiers per workflow;
- prefer mechanical checks;
- require rollback plans for writes;
- record before and after state.

### Public Exposure

An agent may expose a private service through a firewall, reverse proxy, tunnel, or DNS change.

Mitigations:

- classify public exposure as destructive-risk;
- require explicit approval;
- verify exposed ports and URLs;
- document intended audience and auth.

### Data Loss

Storage operations, Docker volume pruning, VM deletion, and snapshot cleanup can destroy data.

Mitigations:

- treat disk, pool, volume, and snapshot deletions as destructive;
- verify backup freshness before risky changes;
- verify restore evidence before trusting a backup;
- distinguish same-node copies from real backups;
- require explicit target identifiers.

### Secret Leakage

Agents may echo secrets into chat, logs, diagnostics, commits, or issue reports.

Mitigations:

- redact by default;
- use credential references;
- scan commits and diagnostics bundles;
- never include full `.env` files.

### Agent Self-Mutation

A local agent may change its own policy, tools, credentials, or model route.

Mitigations:

- treat self-policy changes as approval-gated;
- keep immutable baseline policy outside the agent's writable path where possible;
- record model routing and tool permissions in inventory.
