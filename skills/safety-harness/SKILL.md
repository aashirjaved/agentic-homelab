---
name: safety-harness
description: Apply guardrails before an agent touches homelab infrastructure. Use before any task involving root access, secrets, SSH, Proxmox, Docker, NAS, networking, storage, or power operations.
---

# Safety Harness

## Purpose

Apply guardrails before an agent touches homelab infrastructure.

## When To Use

Use before any task involving root access, secrets, SSH, Proxmox, Docker, NAS storage, networking, firewall rules, or power operations.

## Workflow

1. Classify the requested action by risk.
2. Confirm credentials are scoped to the task.
3. Prefer read-only discovery first.
4. Require approval for write and destructive actions.
5. Capture before and after state.
6. Stop if the tool or command exceeds the approved scope.

## Risk Classification

- `read` - inventory, status, logs, metrics, config inspection.
- `plan` - proposed changes without side effects.
- `write` - restarts, config edits, package installs, VM changes.
- `destructive` - delete, format, prune volumes, expose public ingress, power off critical nodes.
- `credential-access` - reading, rotating, exporting, or using secrets.

## Required Agent Behavior

- Never print secrets back to the user.
- Treat unknown commands as write-risk until classified.
- Prefer APIs with scoped tokens over root SSH.
- Before any approved write, state the exact target, command/tool, expected effect, rollback option, and verifier.
- After execution, verify with an external signal.
