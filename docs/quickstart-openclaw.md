# Quickstart: OpenClaw

1. Choose the skills your homelab needs from `skills/`.
2. Add the relevant MCP servers from `packages/mcp-servers/`.
3. Start with the default policy in `guardrails/policies/default-policy.yaml`.
4. Configure credentials with read-only permissions first.
5. Run an inventory task before approving writes.

Recommended first prompt:

```text
Inventory my homelab in read-only mode, identify missing context, and produce a maintenance plan. Do not make changes.
```

Example config: `examples/local-agent-runtime/openclaw.example.yaml`.

For a persistent local runtime, start from
`templates/agent-runtime/systemd/openclaw.service.example`. Keep secrets in the
referenced protected env file, run as a dedicated non-root user, and begin with
read-only MCP servers.
