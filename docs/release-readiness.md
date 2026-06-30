# Release Readiness Checklist

Use this before tagging a release or recommending the repo to users.

Run the mechanical audit:

```bash
make validate
make release-audit
```

The audit reports `pass`, `fail`, and `manual` items. Manual items require a
real environment or another user; do not market those as verified until they have
actually been run.

## Required

- `make validate` passes.
- README describes current status honestly.
- README includes quick start, safety model, supported domains, supported clients, docs map, and license.
- Changelog and code of conduct are present.
- No real secrets, private IPs tied to a real user, tokens, cookies, or keys are committed.
- Every MCP server has:
  - `README.md`
  - `mcp.yaml`
  - risk levels for every tool
  - approval gates for write/destructive/credential-access tools
  - a read-only path or explicit explanation
- Every example workflow references existing tools.
- Every quickstart tells users to start read-only.
- Bootstrap script creates a starter context without secrets or overwriting by default.
- Workflow chooser recommends only existing example workflows.
- Structured YAML/JSON examples pass the schemas in `schemas/`.
- Named client quickstarts exist for OpenClaw, Hermes, Claude, Codex, Cursor, and Grok.
- Repository org/name/install metadata is declared in `catalog/index.yaml`.
- Source skills include `SKILL.md`, `LICENSE.txt`, and `agents/openai.yaml`.
- Security policy is present.

## Strongly Recommended

- At least one user can run `make validate` from a fresh clone.
- At least one MCP client can load the Claude desktop example after path adjustment.
- Proxmox read-only token docs have been tested against a real non-root token.
- Docker read-only behavior has been tested on a Docker host.
- Diagnostics bundle workflow has been run on macOS and Linux.

## Release Notes Template

```text
## agentic-homelab vX.Y.Z

### Added

### Changed

### Safety Notes

### Verified

### Known Gaps
```
