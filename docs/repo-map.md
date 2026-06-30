# Repo Map

Use this map when deciding where to add new work.

## Add A New MCP Server

1. Create `packages/mcp-servers/<name>/`.
2. Add `README.md`.
3. Add `mcp.yaml`.
4. Mark all tools with risk levels.
5. Require approval for write, destructive, and credential-access tools.
6. Add an example workflow if the server unlocks a common task.
7. Run `python3 scripts/validate_repo.py`.

## Add A New Skill

1. Create `skills/<name>/SKILL.md`.
2. Include purpose, when to use, workflow, safety boundaries, and verification.
3. Prefer references to inventory, policy, and MCP manifests over hardcoded commands.

## Add A New Example

1. Create `examples/<name>/README.md`.
2. Add `workflow.yaml` when the flow can be made machine-readable.
3. Include required skills, MCP servers, approval gates, and verifiers.

## Add A New Policy

1. Create `guardrails/policies/<name>.yaml`.
2. Start conservative.
3. Document the threat or use case.
4. Add catalog metadata when it is intended for users.

## Add A New Template

1. Create `templates/<name>/`.
2. Include a short `README.md`.
3. Use placeholders instead of real hostnames, IPs, tokens, or usernames.
4. Prefer safe defaults that do not mutate systems.
5. Add catalog metadata.
6. Add validation when the template represents a safety boundary.
