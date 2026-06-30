# Quickstart: Claude

Claude-compatible desktop and CLI clients can use this repo as a catalog of MCP servers, skills, and guardrail docs.

Start with:

- `skills/safety-harness`
- the MCP server for your target system
- `guardrails/policies/default-policy.yaml`

Use read-only MCP tools first. Do not enable write, restart, firewall, storage,
public exposure, or credential-access tools until the exact action has been
reviewed and approved.

Keep credentials outside the repo. Prefer API tokens with narrow permissions over shared root passwords.

Example MCP config: `examples/local-agent-runtime/claude-desktop-mcp.example.json`.

Generate a local config with absolute paths:

```bash
python3 scripts/generate_mcp_config.py --inventory homelab.inventory.json --output generated/claude-mcp.json
```

Use the generated `mcpServers` object in Claude Desktop after reviewing the paths and enabled servers.
