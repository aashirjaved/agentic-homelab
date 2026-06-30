# Action Risk Matrix

Use this matrix when deciding whether an agent may run an action now, must stop
for approval, or must treat the request as destructive.

The machine-readable version lives at `guardrails/action-risk-matrix.yaml`.
The guardrail checker can classify both MCP tools and matrix categories:

```bash
python3 scripts/guardrail_check.py network-exposure
python3 scripts/guardrail_check.py storage-risk
python3 scripts/guardrail_check.py destructive
```

| Risk | Default Decision | Examples | Required Evidence |
| --- | --- | --- | --- |
| `read` | allow | Inventory, health checks, bounded logs, DNS/interface inspection, local-only port checks | Read-only command/tool, bounded output, redaction |
| `plan` | allow | Draft update commands, firewall plan, snapshot plan, incident summary | Target, exact proposed action, rollback, verifier, no state change |
| `write` | approval required | Config edits, package updates, container updates, snapshot creation, restarts | Exact human approval, rollback path, external verifier |
| `credential-access` | approval required | Token access, user/permission changes, credential broadening, env reads | Credential reference only, scoped purpose, redaction plan |
| `network-exposure` | approval required | Firewall, route, DNS, VPN, tunnel, reverse proxy, port-forward changes | Intended audience, auth check, exposure scope, rollback |
| `storage-risk` | approval required | Share/mount/dataset/pool/backup changes, snapshot deletion, volume pruning | Backup freshness, restore path, exact target, free-space check |
| `destructive` | separate destructive approval required | Delete resources, format disks, power off infra, wipe diagnostic logs | Human repeats target, backup/no-backup acknowledgement, recovery plan |
| `unknown` | review required | Undeclared tool, ambiguous shell command, unclear target/effect | Classify first, prefer read-only alternative, add policy if recurring |

## How Agents Should Use It

1. Classify the action before execution.
2. If the category is `read` or `plan`, keep output bounded and redacted.
3. If the category requires approval, produce the change plan and stop.
4. If the category is `destructive`, ask for a separate destructive-action
   approval that repeats the exact target.
5. If the category is `unknown`, do not execute it. Use read-only discovery or
   add a manifest/policy entry first.

## Relationship To MCP Manifests

MCP manifests classify specific tools. This matrix classifies real-world actions
that may appear in prompts, shell commands, playbooks, or future integrations.

When they disagree, choose the higher-risk category until the manifest and policy
are updated.
