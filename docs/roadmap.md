# Roadmap

The project should stay practical and safety-first.

## Near Term

- Add real Proxmox API fixtures for more response variants.
- Add Docker Compose file discovery from inventory paths.
- Add diagnostics bundle writer that emits redacted files under `diagnostics/`.
- Add Linux-focused examples for systemd service health.
- Add Headscale/Tailscale ACL review workflow.

## Medium Term

- Add platform-specific NAS adapters for TrueNAS and Synology in read-only mode.
- Add Prometheus/Grafana read-only adapters.
- Add Ansible check-mode playbooks for common setup tasks.
- Add policy tests for approval gates.
- Add example inventories for common homelab shapes.

## Later

- Carefully introduce approved write workflows with dry-run, rollback, and verification.
- Add a policy engine instead of static YAML conventions.
- Add signed release artifacts for MCP server bundles.
- Add richer local-agent runtime supervision examples.

