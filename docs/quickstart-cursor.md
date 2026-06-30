# Quickstart: Cursor

Cursor is useful for editing this repo, writing inventory files, and running local validation. Treat it as a coding agent with shell access, not as a fully trusted infrastructure operator.

## Recommended Flow

1. Open this repository in Cursor.
2. Read `docs/quickstart.md`, `docs/safety-model.md`, and `guardrails/policies/default-policy.yaml`.
3. Create `homelab.inventory.yaml` or `homelab.inventory.json` from the templates.
4. Run validation before and after edits:

```bash
make validate
```

5. Use read-only MCP servers first.

Generate MCP config for clients that support MCP:

```bash
python3 scripts/generate_mcp_config.py --inventory homelab.inventory.json --output generated/mcp-config.json
```

## Starter Prompt

```text
Use this repo's safety model. Read my homelab inventory and the default policy. Use read-only checks only. Do not run writes, restarts, firewall changes, storage changes, public exposure, or credential access without explicit approval. For any proposed change, include target, command/tool, rollback, and verifier.
```

## Cursor-Specific Notes

- Keep real `.env` files ignored.
- Do not paste secrets into chat.
- Prefer editing inventory, policies, and workflow YAML over running one-off shell commands.
- Use `make validate` as the repo health check.
