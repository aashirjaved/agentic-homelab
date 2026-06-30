# Example: Docker Stack Maintenance

Goal: let an agent inspect Docker stacks, identify unhealthy containers, and plan updates.

## Flow

1. Enable Docker MCP read-only tools.
2. Gather container, image, network, and volume inventory.
3. Review update candidates.
4. Require approval before restarts, pulls, removes, or volume changes.

