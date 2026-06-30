# Credential Patterns

Never store real secrets in this repository.

## Credential References

Use references in inventory and examples:

```yaml
credential_ref: proxmox-readonly
```

The actual value should live in a password manager, OS keychain, agent secret store, `.env` file outside git, or platform-specific vault.

## Recommended Scopes

- Proxmox: read-only token for inventory; separate approval-gated token for lifecycle actions.
- Docker: read-only socket proxy where possible; avoid raw Docker socket for untrusted agents.
- NAS: read-only health user; separate admin account for share or disk changes.
- Monitoring: read-only query token; separate token for alert silencing.
- Networking: read-only diagnostics first; firewall/router changes require human approval.

## Redaction Rules

Agents should never print:

- passwords,
- private keys,
- API tokens,
- cookie/session values,
- full `.env` files,
- recovery codes.

Agents may print:

- credential reference names,
- scopes,
- expiration dates,
- last rotation timestamp,
- whether a credential is present.

