# Roadmap

The project should stay practical and safety-first.

## North Star

Install it and ask your homelab what is wrong:

1. **Map** — the agent auto-discovers your lab (network, Proxmox, Docker,
   NAS, monitoring) and generates the inventory instead of you hand-editing
   YAML.
2. **Explain** — correlate graph relationships, live health, evidence quality,
   and changes into ranked, falsifiable incident hypotheses.
3. **De-risk** — assess restoration and updates from evidence, blast radius,
   rollback, and independent verification rather than optimistic status flags.
4. **Share** — create a useful, safely redacted diagnostic artifact for support
   communities without exposing raw inventory or credentials.

The doctor already implements the first coherent version of this loop. Future
work deepens its evidence: scheduled read-only patrols for disk and SMART health,
   backup freshness, update lag, CVE exposure of running images, cert expiry,
   drift against the inventory. Daily digest, zero writes.

Nothing on this roadmap requires write access. Approval-gated remediation may
follow only after the diagnosis engine earns trust.

## Near Term

- Add real Proxmox API fixtures for more response variants.
- Add Docker Compose file discovery from inventory paths.
- Add more Proxmox task and storage response variants.
- Add vendor-specific TrueNAS and Synology details behind the vendor-neutral probe model.
- Add Linux-focused examples for systemd service health.
- Add Headscale/Tailscale ACL review workflow.

## Medium Term

- Add platform-specific NAS enrichment for TrueNAS and Synology in read-only mode.
- Add Prometheus/Grafana read-only adapters.
- Add Ansible check-mode playbooks for common setup tasks.
- Add policy tests for approval gates.
- Add example inventories for common homelab shapes.

## Later

- Carefully introduce approved write workflows with dry-run, rollback, and verification.
- Add a policy engine instead of static YAML conventions.
- Add signed release artifacts for MCP server bundles.
- Add richer local-agent runtime supervision examples.
