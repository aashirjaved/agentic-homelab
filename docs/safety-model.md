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

## Enforcement Model

Be precise about what is mechanically enforced versus what is convention:

- **Enforced by code:** the reference MCP servers implement zero write tools —
  a client cannot invoke what does not exist. Known-destructive command
  patterns (`rm -rf`, `mkfs`, `zfs destroy`, ...) are force-classified as
  destructive by `scripts/guardrail_check.py` regardless of how the action is
  labeled.
- **Enforced in CI:** `make validate` checks that every manifest-declared
  write/destructive/credential tool carries `requires_approval`, and exercises
  the guardrail checker.
- **Advisory (honor system):** an agent must voluntarily run the guardrail
  checker before acting, and it self-reports the action label. Nothing in this
  repo intercepts tool calls at runtime. If your client supports execution
  hooks (for example Claude Code `PreToolUse`), wire the checker in as a real
  gate — a ready-made hook script ships at
  `guardrails/hooks/pretooluse-guardrail.sh`.

This residual trust gap — the agent choosing the label — is the boundary of
what a convention-based system can do. Treat manifest risk labels as trusted
input reviewed by humans.

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
