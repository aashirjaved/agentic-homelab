# Implemented Capabilities

This repo is intentionally honest about what works today.

## Homelab Intelligence Doctor

The packaged `homelab` CLI provides the product-facing, read-only experience
(`scripts/homelab_doctor.py` remains as a compatibility wrapper):

- no-argument discovery for the local host, Docker, filesystem capacity, DNS,
  and Tailscale state;
- optional scoped Proxmox discovery for nodes, guests, storage, and tasks;
- vendor-neutral service and NAS HTTP health probes that retain no URL/body;
- a Homelab Graph spanning nodes, services, storage, Compose stacks, Docker
  networks, inferred mount backing, and dependencies;
- ranked incident hypotheses, blast radius, evidence, and verification steps;
- a bounded semantic “what changed?” timeline;
- per-service recovery readiness and human-controlled update intelligence;
- Markdown, JSON, redacted single-report, and four-file diagnostic bundle output.

The doctor performs no infrastructure writes. Its only writes are explicitly
requested local history and report/bundle artifacts.

## Implemented Reference MCP Servers

All reference servers are read-only by default and are smoke-tested by `make validate`.

| Domain | Server | Implemented Tools | Writes Implemented |
| --- | --- | --- | --- |
| Proxmox | `packages/mcp-servers/proxmox/server.py` | `list_nodes`, `list_guests`, `get_guest_config`, `list_storage`, `list_recent_tasks` | No |
| Docker | `packages/mcp-servers/docker/server.py` | `list_containers`, `inspect_container`, `list_compose_projects`, `list_volumes`, `read_container_logs`, `plan_stack_update` | No |
| Networking | `packages/mcp-servers/networking/server.py` | `inspect_interfaces`, `inspect_dns`, `inspect_tailnet`, `scan_local_services`, `plan_firewall_change` | No |
| Storage/NAS | `packages/mcp-servers/storage-nas/server.py` | `list_disks`, `read_smart_health`, `list_pools`, `check_backup_freshness`, `plan_share_change` | No |
| Monitoring | `packages/mcp-servers/monitoring/server.py` | `list_alerts`, `query_metrics`, `read_logs`, `build_incident_summary` | No |
| VM Management | `packages/mcp-servers/vm-management/server.py` | `list_vms`, `inspect_vm`, `plan_snapshot` | No |

## Implemented Safety Assets

- Default guardrail policy.
- Action risk matrix for prompts, shell commands, playbooks, and MCP tools.
- Guardrail checker classifies both MCP tool names and action-risk categories.
- Model-routing example.
- Credential patterns.
- Threat model.
- Safety harness skill.
- Source skills include `SKILL.md`, `LICENSE.txt`, and `agents/openai.yaml`
  interface metadata.
- Read-only workflow examples.
- Read-only backup restore drill workflow.
- Day-two maintenance loop.
- Read-only Ansible audit playbook.
- Local agent runtime service templates.
- Copyable `AGENTS.md` operating contract for user homelab repos.
- Bootstrap script for creating a starter homelab agent context directory.
- Workflow chooser that recommends read-only starter examples from inventory.
- Client compatibility matrix and quickstarts for OpenClaw, Hermes, Claude,
  Codex, Cursor, and Grok.
- Validation and MCP smoke tests.
- Release audit command that separates mechanically checked items from manual
  real-environment verification.
- Release-facing README, documentation index, changelog, code of conduct,
  contributing guide, security policy, license, and GitHub validation workflow.

## Intentionally Not Implemented

The reference servers do not implement:

- VM/container deletion.
- Power operations.
- Disk formatting.
- Docker pruning.
- Firewall writes.
- Public service exposure.
- Credential rotation.
- Alert silencing.
- Monitoring config changes.

Those operations are represented in manifests so agents can reason about risk, but they should remain approval-gated and platform-specific.

## What `make validate` Proves

- Catalog paths exist.
- MCP manifests include required fields.
- MCP package READMEs include standard usage, configuration, smoke test, and safety sections.
- Write/destructive/credential-access tools require approval.
- Inventory template has required top-level shape.
- Accidental secret patterns are not present in docs/config examples.
- Each reference MCP server initializes and exposes expected tools.
- Proxmox API formatting and redaction logic are tested with fixtures.
- Example workflows reference real skills, MCP servers, and tool names.
- Read-only Ansible audit assets avoid known write-capable modules and commands.
- Local agent runtime service templates include basic least-privilege fields.
- Bootstrap output includes inventory, policy, action matrix, agent instructions,
  maintenance log, and diagnostics placeholder.
- Workflow chooser output references existing example workflow files.
- JSON Schema validation covers inventory templates, MCP manifests, guardrail
  policies, example workflows, and the action risk matrix.
- Validation requires quickstart coverage for the named agent/client families.
- Release audit reports pass/fail/manual evidence for publishing readiness.
- Release docs include required OSS rollout sections and are cataloged.

## What `make validate` Does Not Prove

- Your Proxmox token has the correct permissions.
- Docker daemon is reachable on your host.
- SMART health is available for every disk.
- Tailscale is installed or authenticated.
- Your backups are restorable.
- A service is safe to restart.

Agents should treat validation as repo health, not homelab health.
