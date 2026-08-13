# Roadmap

The project should stay practical and safety-first.

## North Star

Install it, and your agent of choice earns its way from observer to operator:

1. **Map** — the agent auto-discovers your lab (network, Proxmox, Docker,
   NAS, monitoring) and generates the inventory instead of you hand-editing
   YAML.
2. **Monitor 24/7** — scheduled read-only patrols: disk and SMART health,
   backup freshness, update lag, CVE exposure of running images, cert expiry,
   drift against the inventory. Daily digest, zero writes.
3. **Propose** — findings become concrete approval requests: patch container
   X, rotate cert Y, each with rollback and verifier attached.
4. **Earned autonomy** — narrow, pre-declared action classes get auto-approved
   via policy (for example, canary-VM updates with automatic rollback), one
   class at a time, only after the human has watched the agent do it right.

Autonomy is a ladder, not a switch. Nothing on this roadmap skips the
approval model — it widens what the human has explicitly delegated.

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

