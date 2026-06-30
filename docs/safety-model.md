# Safety Model

Agents should operate homelabs in layers.

## 1. Observe

Read-only tools gather inventory, health, logs, versions, and topology.

## 2. Explain

The agent summarizes findings and identifies uncertainty.

## 3. Plan

The agent proposes exact commands, API calls, or configuration changes.

## 4. Approve

The human approves risky or state-changing actions.

## 5. Execute

The agent performs the approved action with scoped credentials.

## 6. Verify

The agent checks the result and records what changed.

## Default Deny

Any operation not explicitly categorized should be treated as risky. Power operations, deletes, disk formatting, firewall changes, user changes, and credential changes require explicit human approval.

Use [action-risk-matrix.md](action-risk-matrix.md) for concrete categories,
examples, and evidence requirements. The same matrix is available as
`guardrails/action-risk-matrix.yaml` for agents and future tooling.

## Guardrail Check CLI

Use the guardrail checker before an agent runs a tool:

```bash
python3 scripts/guardrail_check.py list_nodes
python3 scripts/guardrail_check.py delete_guest --server proxmox
python3 scripts/guardrail_check.py network-exposure
python3 scripts/guardrail_check.py destructive
python3 scripts/guardrail_check.py unknown_action
```

Possible decisions:

- `allow_readonly` - declared read/plan action; keep output bounded and redacted.
- `approval_required` - declared write/destructive/credential action; human approval is required.
- `destructive_approval_required` - destructive matrix category; require separate approval that repeats the exact target.
- `unknown_requires_review` - not declared in manifests; treat as write-risk until classified.
