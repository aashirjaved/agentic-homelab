# Client Compatibility

This repo is client-agnostic. Use the same operating model with local agents,
desktop MCP clients, and coding agents:

1. load inventory, policy, and workflow context;
2. start read-only;
3. plan before any write;
4. require explicit approval for risky actions;
5. verify externally.

| Client | Best Use | Start Here | Notes |
| --- | --- | --- | --- |
| OpenClaw | Local homelab agent running near the infrastructure | `docs/quickstart-openclaw.md` | Use service templates and read-only MCP manifests first. |
| Hermes | Local agent runtime and maintenance assistant | `docs/quickstart-hermes.md` | Treat the runtime as managed infrastructure with logs and health checks. |
| Claude | Desktop/client MCP operator | `docs/quickstart-claude.md` | Generate MCP config with absolute paths before enabling servers. |
| Codex | Repo editing, validation, scripts, workflow authoring | `docs/quickstart-codex.md` | Keep shell work read-only unless an exact change is approved. |
| Cursor | Coding-agent editing and validation | `docs/quickstart-cursor.md` | Prefer inventory, policy, and workflow edits over ad hoc infra commands. |
| Grok | Reference/planning assistant | `docs/quickstart-grok.md` | Use for planning and review unless your runtime has safe tool boundaries. |

## Common Client Setup

All clients should receive:

- `AGENTS.md` from `templates/agent-instructions/`;
- `homelab.inventory.yaml` or `homelab.inventory.json`;
- `guardrails/policies/default-policy.yaml`;
- `guardrails/action-risk-matrix.yaml`;
- one example workflow selected with `scripts/choose_workflow.py`.

## Common First Prompt

```text
Read the inventory, AGENTS.md, the default guardrail policy, and the selected
workflow. Use read-only discovery only. Do not make changes. Return findings,
missing context, risks, and the verifier required before any future approved
change.
```

## Client Capability Levels

- **Reference-only**: can read docs and propose plans, but cannot run tools.
- **Repo operator**: can edit files and run validation locally.
- **Read-only infrastructure operator**: can call read-only MCP tools.
- **Approval-gated operator**: can run approved writes one action at a time.

Begin every client at the lowest useful level.
