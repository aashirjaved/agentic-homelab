# Quickstart: Hermes

Use Hermes as a local homelab agent with read-only MCP tools first.

1. Enable only inventory and health-check tools.
2. Mount `skills/safety-harness` and the skill relevant to the task.
3. Point Hermes at the default guardrail policy.
4. Require approval for host writes, restarts, and credential access.

Example config: `examples/local-agent-runtime/hermes.example.yaml`.

For a persistent local runtime, start from
`templates/agent-runtime/systemd/hermes.service.example`. Keep secrets in the
referenced protected env file, run as a dedicated non-root user, and begin with
read-only MCP servers.
