# Homelab Agent Instructions

These instructions apply to any AI agent working in this homelab repository.

## Operating Model

Use the observe, plan, approve, execute, verify loop.

1. Read the inventory, guardrail policy, and relevant workflow before touching a system.
2. Observe read-only state first.
3. Separate facts, assumptions, and guesses.
4. Produce a plan before any write.
5. Wait for explicit human approval before writes, restarts, credential access,
   public exposure, or destructive actions.
6. Execute one bounded change at a time.
7. Verify with an external signal and record the result.

## Required Context

Before operating, read the relevant files if they exist:

- `<inventory-path>`
- `<guardrail-policy-path>`
- `<maintenance-log-path>`
- `<diagnostics-dir>`
- `<mcp-config-path>`
- `<workflow-path>`

If a file is missing, say what is missing and continue only with read-only
discovery that does not require it.

## Default Permissions

When classifying an action, use the local policy and action risk matrix if they
exist. If classification is unclear, treat the action as `unknown` and stop for
review.

Allowed without extra approval:

- read inventory and documentation;
- list nodes, guests, containers, disks, alerts, services, and recent tasks;
- read bounded logs;
- inspect DNS, interfaces, routes, and local-only service ports;
- generate plans and rollback proposals;
- create redacted diagnostics bundles.

Requires explicit approval:

- editing files outside temporary/generated diagnostics output;
- restarting services, containers, VMs, or hosts;
- changing firewall, DNS, routing, VPN, ingress, or public exposure;
- changing storage, shares, mount points, snapshots, or backup jobs;
- changing credentials, tokens, users, permissions, or secret stores;
- applying package updates or container image updates;
- enabling new MCP servers or broadening tool permissions.

Forbidden unless the human gives a separate destructive-action approval:

- deleting VMs, containers, volumes, snapshots, datasets, or backups;
- formatting disks or changing partitions;
- pruning Docker resources;
- powering off infrastructure;
- wiping logs that are needed for diagnosis;
- exposing a private service to the public internet.

## Secret Handling

Do not print, copy, store, or summarize secret values.

Use credential references instead of values:

- password manager item names;
- environment variable names;
- OS keychain labels;
- secret store paths;
- scoped API token labels.

If a command or file would reveal a secret, stop and ask for a safer path.

## Change Plan Format

Before any approved change, produce:

```text
Target:
Current evidence:
Proposed action:
Command or tool:
Risk:
Expected effect:
Rollback:
Verifier:
Approval needed:
```

Do not execute the command or tool until the human approves that exact action.

## Verification

Use at least one external verifier after a change:

- Proxmox task status;
- container health status;
- service status and recent logs;
- HTTP health check;
- storage pool or SMART health;
- monitoring alert state;
- user-visible application behavior.

If verification fails, stop and produce a recovery plan.

## Reporting

End each maintenance task with:

```text
Scope:
Actions taken:
Approval received:
Verification:
Residual risk:
Follow-up:
```

Keep the report concise and cite the evidence used.
