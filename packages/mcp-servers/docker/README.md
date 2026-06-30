# Docker MCP Server

MCP interface for Docker hosts, Compose stacks, containers, volumes, and images.

## Initial Scope

- list containers, images, networks, and volumes
- inspect Compose projects
- detect unhealthy containers
- plan image updates and restarts
- execute approved maintenance actions in a future milestone

## Implemented Read-Only Tools

- `list_containers`
- `inspect_container`
- `list_compose_projects`
- `list_volumes`
- `read_container_logs`
- `plan_stack_update`

## Smoke Test

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python3 packages/mcp-servers/docker/server.py
```

The reference server implements read-only Docker discovery through the Docker CLI. It does not implement write or destructive tools.

## Configuration

- Requires Docker CLI for live host discovery.
- Works without Docker for MCP tool-list smoke tests.
- Keep Docker socket access scoped to the host you intend to inspect.

## Safety Contract

Default mode is read-only. Container removal, volume removal, image pruning, and stack restarts require approval.
