# Changelog

All notable changes to `agentic-homelab` will be documented here.

This project uses a pragmatic release log. Keep entries focused on user-visible
changes, safety changes, and compatibility notes.

## Unreleased

- Nothing yet.

## 0.2.0 - 2026-08-14

### Added

- Inferred Docker Compose stacks, Compose dependencies, Docker networks, named
  volumes, container bind-mount backing storage, and NFS/SMB serving hosts.
- Explicit unresolved topology relationships when a bind mount, Compose
  dependency, or storage server cannot be connected safely.
- Installable `agentic-homelab` Python package and `homelab` command with
  `doctor`, `investigate`, `changes`, `recovery`, `updates`, and `share` entrypoints.
- Proxmox guest-disk inference connecting VM and LXC configuration to Proxmox
  storage backends.
- Reproducible incident-investigation demo generated from the real CLI.

### Changed

- Product language now distinguishes observed evidence from declared recovery
  and update metadata, and documents the deterministic investigator boundary.
- The README hero now demonstrates incident investigation instead of guardrails.
- Each CLI subcommand now has a focused human and JSON output contract.

## 0.1.1 - 2026-08-13

### Fixed

- `make validate` no longer fails on a fresh clone (restored `Unreleased`
  changelog section required by the release audit) and validation failures now
  print the failing audit items instead of an empty message.
- MCP servers respond to failed tool calls with the request id and `isError`
  instead of `id: null` protocol errors that hang clients.
- Manifest-declared destructive tools now receive the stricter
  `destructive_approval_required` decision with the evidence checklist.

### Added

- Known-destructive command patterns (`rm -rf`, `mkfs`, `zfs destroy`, ...) are
  force-classified as destructive regardless of the supplied label.
- `generate_mcp_config.py --env` bakes `PROXMOX_*` credentials into configs for
  desktop MCP clients.
- Claude Code `PreToolUse` hook (`guardrails/hooks/pretooluse-guardrail.sh`)
  turning the guardrail checker into a mechanical gate, and an Enforcement
  Model section in the safety docs.
- YAML frontmatter in all `SKILL.md` files for skills-ecosystem discovery.

### Changed

- README: venv activation step in Quick Start, exit-code contract note,
  defensible read-only headline, plain v0.1 status wording.

## 0.1.0 - 2026-08-13

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
