# Agent Self Management

## Purpose

Help local agents manage their own runtime safely without taking over the host.

## When To Use

Use for OpenClaw, Hermes, Claude-compatible agents, Codex-like agents, local model workers, background services, and agent credential hygiene.

## Workflow

1. Inspect runtime process, service files, logs, and configuration.
2. Check available permissions and policy boundaries.
3. Plan updates, restarts, or model changes.
4. Require approval before service restarts, credential changes, or package updates.
5. Verify the agent is responsive after changes.

## Agent Runtime Inventory

Record:

- runtime name and version,
- service manager,
- config path,
- log path,
- model routes,
- MCP servers,
- filesystem permissions,
- network permissions,
- credential references,
- health check command.

## Safety Notes

- Agents are services, not magic. They need logs, health checks, restart policy, and rollback.
- Model routing must be explicit. Generation, embeddings, vision, and verification can have different privacy rules.
- Do not let an agent edit its own policy or credentials without human approval.
