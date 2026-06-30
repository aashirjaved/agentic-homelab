# Security Policy

`agentic-homelab` is built around the assumption that homelabs contain sensitive systems: credentials, storage, media, personal data, internal networks, and administrative interfaces.

## Supported Security Model

- Read-only discovery before mutation.
- Least-privilege credentials.
- Explicit approval for writes, destructive operations, network exposure, and credential access.
- Redaction by default.
- External verification for completed work.

## Report A Vulnerability

Open a private security advisory or contact the maintainers through the repository owner profile. Do not include real credentials, private keys, or personal infrastructure details in public issues.

## High-Risk Changes

These changes should always require human approval:

- deleting VMs, containers, datasets, snapshots, or volumes;
- formatting disks or changing pools;
- exposing services publicly;
- changing firewall, route, DNS, or VPN rules;
- reading, exporting, rotating, or writing credentials;
- restarting critical services;
- changing agent policies, model routes, or permissions.

## Maintainer Rule

No example, test, fixture, screenshot, or diagnostics bundle should contain a real password, token, private key, cookie, session value, recovery code, or private IP tied to a real user's lab.

