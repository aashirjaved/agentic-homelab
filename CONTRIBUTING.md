# Contributing

Thanks for helping make homelabs easier for agents to operate safely.

## Contribution Types

- MCP server integrations
- Agent skills
- Guardrail policies
- Example workflows
- Infrastructure playbooks
- Docs and compatibility notes

## Expectations

Every integration should be safe to inspect before it is safe to mutate.

Required for new MCP servers:

- README with setup and permissions
- read-only mode
- tool list with risk levels
- example config
- failure behavior
- catalog entry

Required for new skills:

- `SKILL.md`
- supported agents
- required tools
- safety boundaries
- example prompts

## Risk Levels

- `read` - inspection only
- `plan` - produces proposed changes
- `write` - changes configuration or state
- `destructive` - deletes, powers off, reformats, wipes, or revokes access

Destructive tools must require explicit approval in their MCP contract and documentation.

