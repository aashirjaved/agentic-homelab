# Changelog

All notable changes to `agentic-homelab` will be documented here.

This project uses a pragmatic release log. Keep entries focused on user-visible
changes, safety changes, and compatibility notes.

## 0.1.0 - Unreleased

### Added

- Read-only reference MCP servers for Proxmox, Docker, storage/NAS, networking,
  monitoring, and VM management.
- Agent skills for setup, infrastructure maintenance, agent self-management, and
  safety harness workflows.
- Default guardrail policy, action risk matrix, and model-routing example.
- Machine-readable workflows for Proxmox maintenance, Docker stack maintenance,
  NAS/media checks, backup restore drills, multi-node monitoring, diagnostics,
  and local agent runtime maintenance.
- Inventory, agent-instruction, diagnostics, MCP server, skill, and local-agent
  service templates.
- Bootstrapper, workflow chooser, guardrail checker, diagnostics bundle
  generator, doctor, MCP config generator, validator, and release audit.
- Quickstarts for OpenClaw, Hermes, Claude, Codex, Cursor, and Grok.

### Safety Notes

- Reference MCP servers are read-only by default.
- Writes, destructive actions, credential access, network exposure, storage
  changes, and service restarts require explicit approval.
- Release audit separates mechanically verified items from manual real-world
  checks.

### Known Gaps

- Real Proxmox, Docker, and cross-platform diagnostics checks must be verified
  in live environments before broad compatibility claims.
- Approved write workflows are intentionally deferred until read-only behavior is
  proven in more setups.
