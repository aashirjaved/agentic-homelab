# Monitoring MCP Server

MCP interface for metrics, logs, alerts, and incident triage.

## Initial Scope

- query metrics and alert state
- summarize logs
- identify affected services
- prepare remediation plans

## Implemented Read-Only Tools

- `list_alerts`
- `query_metrics`
- `read_logs`
- `build_incident_summary`

## Smoke Test

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python3 packages/mcp-servers/monitoring/server.py
```

Implemented read-only tools inspect host metrics, bounded service logs, optional `ALERT_URLS` health endpoints, and incident triage plans. It does not silence alerts, restart services, or change monitoring configuration.

## Configuration

- `ALERT_URLS` can list comma-separated health endpoints for read-only checks.
- Log reads are bounded by the server schema.
- Missing local tools degrade to explanatory output instead of writes.

## Safety Contract

Default mode is read-only. Muting alerts, changing scrape configs, deleting logs, and restarting services require approval.
