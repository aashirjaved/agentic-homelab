# Quickstart: Codex

Use Codex as a repo operator for agentic homelab work: editing inventories,
guardrails, workflows, scripts, docs, and validation. Treat shell access as
powerful and keep infrastructure operations read-only unless the user approves an
exact action.

## Recommended Flow

1. Read `AGENTS.md` if present.
2. Read `docs/quickstart.md`, `docs/safety-model.md`, and
   `docs/action-risk-matrix.md`.
3. Create or update inventory from `templates/inventory/`.
4. Choose a workflow:

```bash
python3 scripts/choose_workflow.py --inventory homelab.inventory.yaml
```

5. Run validation after repo edits:

```bash
make validate
```

6. Use MCP tools in read-only mode first.

## Starter Prompt

```text
Use this repo as the operating manual for my homelab. Read AGENTS.md,
homelab.inventory.yaml, guardrails/policies/default-policy.yaml, and the selected
workflow. Use read-only discovery only. Do not make writes, restarts, firewall
changes, public exposure, storage changes, VM lifecycle changes, or credential
access without explicit approval. Any change plan must include target, command or
tool, rollback, and verifier.
```

## Codex-Specific Notes

- Prefer `make validate`, `scripts/doctor.py`, and read-only MCP tools over
  direct shell exploration.
- Never print secrets from `.env`, shell history, service configs, or diagnostic
  bundles.
- Keep generated outputs in ignored directories such as `generated/` and
  `diagnostics/`.
- Do not broaden MCP server permissions while debugging an unrelated issue.
