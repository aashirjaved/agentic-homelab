# Codex Starter Prompt

Use this repository as your operating context for homelab work.

1. Read `docs/quickstart.md`.
2. Read `docs/safety-model.md`.
3. Read `guardrails/policies/default-policy.yaml`.
4. Read `homelab.inventory.yaml` if present, otherwise ask the user to create it from `templates/inventory/homelab.inventory.example.yaml`.
5. Use read-only discovery first.
6. Do not print secrets.
7. Do not make writes, restarts, firewall changes, storage changes, VM lifecycle changes, or credential changes without explicit approval.
8. For any approved change, state the verifier before executing.

