# Cursor Starter Prompt

Use this repository as the operating manual for homelab work.

Read:

- `docs/quickstart.md`
- `docs/safety-model.md`
- `docs/credential-patterns.md`
- `guardrails/policies/default-policy.yaml`

Rules:

- Start with read-only discovery.
- Do not print secrets.
- Do not make writes, restarts, firewall changes, public exposure, storage changes, VM lifecycle changes, or credential changes without explicit approval.
- Prefer changing inventory/policy/workflow files over ad hoc commands.
- Run `make validate` after repo edits.
- Every proposed change needs a verifier.

