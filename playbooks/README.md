# Playbooks

Reproducible infrastructure starters live here.

- `ansible/` - read-only audits first, then host setup once reviewed
- `terraform/` - infrastructure definitions where providers exist
- `kubernetes/` - manifests, Helm values, and GitOps examples

Playbooks should be safe to run in check or plan mode before applying.

Start with `ansible/read-only-audit.yml`. It gathers facts and health signals without
installing packages, restarting services, editing files, or changing host state.
