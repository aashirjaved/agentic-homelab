# Maintenance Loop

Use this loop for recurring homelab work: weekly health checks, upgrade prep,
alert triage, backup review, and local agent runtime maintenance.

## 1. Declare Scope

Pick one target and one outcome.

Good scopes:

- "Check Proxmox node health and storage pressure."
- "Review Docker media stack drift before updates."
- "Confirm NAS backup freshness and obvious disk warnings."
- "Check whether the last backup has restore-test evidence."
- "Triage monitoring alerts from the last 24 hours."
- "Inspect the local Hermes service without restarting it."

Avoid broad prompts like "fix my homelab." They hide risk and make approval
boundaries fuzzy.

## 2. Load Context

The agent should read:

- `homelab.inventory.yaml`;
- the relevant quickstart;
- `guardrails/policies/default-policy.yaml`;
- the relevant example workflow;
- current diagnostics or monitoring output.

Inventory files should name systems and credential references, not secrets.

## 3. Observe Only

First pass actions should be read-only:

- list nodes, guests, containers, disks, alerts, services, and recent tasks;
- read bounded logs;
- check backup timestamps;
- inspect local network state;
- gather facts with `playbooks/ansible/read-only-audit.yml` when Ansible is used.

The output should separate facts from guesses.

## 4. Produce A Plan

The agent should produce:

- findings ranked by impact;
- uncertainty and missing context;
- proposed actions;
- commands or MCP tools to run;
- expected effect;
- rollback path;
- verification checks;
- approval required.

Plans are not approvals.

## 5. Approve One Change

Approve a single bounded change at a time. Prefer changes that can be verified
quickly and rolled back.

Approval text should include:

```text
Target:
Action:
Risk:
Expected effect:
Rollback:
Verifier:
Time window:
```

Do not batch destructive operations with routine maintenance.

## 6. Verify Externally

After a change, verify with a signal outside the agent's reasoning:

- Proxmox task status;
- container health;
- service logs;
- HTTP health check;
- SMART or pool status;
- monitoring alert state;
- user-visible app behavior.

If verification fails, stop and produce a recovery plan before trying another
change.

## 7. Record The Result

Keep a short maintenance note:

```text
Date:
Operator:
Agent/client:
Target:
Change:
Approval:
Verifier:
Result:
Follow-up:
```

These notes become future context and reduce repeated rediscovery.
