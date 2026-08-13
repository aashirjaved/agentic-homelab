# agentic-homelab

[![Validate](https://github.com/aashirjaved/agentic-homelab/actions/workflows/validate.yml/badge.svg)](https://github.com/aashirjaved/agentic-homelab/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Safety: read-only first](https://img.shields.io/badge/safety-read--only%20first-blue.svg)](docs/safety-model.md)

**Give AI agents safe, read-only access to your homelab — with approval gates
ready for when you add writes.** Skills, MCP servers, guardrails, templates,
and workflows for Proxmox, Docker, NAS, and monitoring. The reference servers
observe and plan; they deliberately implement zero write operations.

> Practical over hype. Read-only first. Human-approved writes. Mechanical verification.

![Guardrail demo: reads flow, risky actions stop for approval](docs/assets/demo.gif)

```console
$ python3 scripts/guardrail_check.py destructive
action: destructive
server: None
decision: destructive_approval_required
risk: destructive
required_evidence:
- separate destructive-action approval
- target identifier repeated by the human
- verified backup or explicit no-backup acknowledgement
- recovery plan
next_step: Stop for separate destructive-action approval that repeats the exact target and verifier.
```

Every action an agent wants to take is classified before it runs. Reads flow
freely; writes stop and ask; destructive operations demand a backup and a
human repeating the exact target.

## What This Is

`agentic-homelab` is an open-source starter kit for making a homelab
agent-friendly without handing an agent unlimited root access.

It gives agents structured context, read-only tools, explicit approval gates, and
verification patterns for common homelab setups:

- Proxmox and VM-heavy labs;
- Docker and Compose stacks;
- media servers and NAS storage;
- monitoring and incident triage;
- multi-node local networks;
- local agents such as OpenClaw and Hermes;
- coding-agent clients such as Claude, Codex, Cursor, and Grok.

## What This Is Not

- Not a turnkey autopilot for your infrastructure.
- Not a replacement for backups, restore testing, or human approval.
- Not a collection of root shell prompts.
- Not a claim that every write operation is implemented or safe.

The reference MCP servers are read-only by default. Risky operations are
represented in manifests and guardrails so agents can plan and ask for approval,
but the reference implementations intentionally avoid destructive writes.

## Why This Exists

Homelabs are personal infrastructure: hypervisors, NAS boxes, media servers,
Docker hosts, monitoring stacks, local agents, VPNs, and private data. Agents can
help maintain them, but only when they have clear context, scoped tools, and
strong boundaries.

The goal is simple: make the safe path the easy path.

## Quick Start

Clone the repo, validate it, then bootstrap a starter context for your own lab:

```bash
git clone https://github.com/aashirjaved/agentic-homelab.git
cd agentic-homelab
make validate                  # creates .venv and installs dependencies
source .venv/bin/activate      # required for the python3 commands below
python3 scripts/bootstrap_homelab_repo.py /path/to/your/homelab-agent-context
```

Install the skills bundle with the same GitHub shorthand convention used by
modern skills repos:

```bash
npx skills add aashirjaved/agentic-homelab --yes
```

Each source skill is self-contained with `SKILL.md`, `LICENSE.txt`, and
`agents/openai.yaml` metadata for agent ecosystems that support it.

Then edit:

- `/path/to/your/homelab-agent-context/homelab.inventory.yaml`
- `/path/to/your/homelab-agent-context/AGENTS.md`
- `/path/to/your/homelab-agent-context/guardrails/policies/default-policy.yaml`

Pick a safe first workflow:

```bash
python3 scripts/choose_workflow.py --inventory /path/to/your/homelab-agent-context/homelab.inventory.yaml
```

Classify actions before running them:

```bash
python3 scripts/guardrail_check.py list_nodes
python3 scripts/guardrail_check.py network-exposure
python3 scripts/guardrail_check.py destructive
```

Exit codes are part of the contract: `0` means allow read-only, `2` means stop
for approval — so the last two commands exiting `2` is the guardrail working,
not a crash.

## What Is Included

| Area | Purpose |
| --- | --- |
| `packages/mcp-servers/` | Read-only reference MCP servers and manifests for Proxmox, Docker, storage/NAS, networking, monitoring, and VM management. |
| `skills/` | Agent skills for setup, infrastructure maintenance, agent self-management, and safety. |
| `guardrails/` | Default policy, model routing example, and action risk matrix. |
| `examples/` | Machine-readable workflows for Proxmox, Docker, NAS/media, monitoring, local agents, diagnostics, and backup restore drills. |
| `templates/` | Inventory starters, agent instructions, diagnostics format, and local-agent service templates. |
| `schemas/` | JSON Schemas for inventory, MCP manifests, guardrail policies, workflows, and action risk matrix. |
| `scripts/` | Validation, MCP smoke tests, diagnostics bundle generation, workflow chooser, guardrail checker, bootstrapper, doctor, and release audit. |
| `docs/` | Quickstarts, safety model, threat model, architecture patterns, credential patterns, and release readiness. |

## Safety Model

Agents should follow this loop:

1. **Observe** read-only state.
2. **Explain** findings and uncertainty.
3. **Plan** exact changes, rollback, and verifier.
4. **Approve** one risky action at a time.
5. **Execute** only the approved action.
6. **Verify** using external evidence.
7. **Record** the result.

Default-deny categories include writes, destructive actions, credential access,
network exposure, storage changes, public ingress, service restarts, and agent
self-mutation.

Start with:

- [docs/safety-model.md](docs/safety-model.md)
- [docs/action-risk-matrix.md](docs/action-risk-matrix.md)
- [docs/threat-model.md](docs/threat-model.md)
- [templates/agent-instructions/AGENTS.md](templates/agent-instructions/AGENTS.md)

## Supported Domains

| Domain | Status | Primary Assets |
| --- | --- | --- |
| Proxmox | Read-only reference server | `packages/mcp-servers/proxmox`, `docs/proxmox-readonly-token.md`, `examples/proxmox-vm-maintenance` |
| Docker/Compose | Read-only reference server | `packages/mcp-servers/docker`, `examples/docker-stack-maintenance` |
| Storage/NAS | Read-only reference server | `packages/mcp-servers/storage-nas`, `examples/media-server-nas`, `examples/backup-restore-drill` |
| Networking | Read-only diagnostics and plan tools | `packages/mcp-servers/networking`, `guardrails/action-risk-matrix.yaml` |
| Monitoring | Read-only metrics/logs/alerts and incident summaries | `packages/mcp-servers/monitoring`, `examples/multi-node-monitoring` |
| VM management | Read-only inventory and snapshot planning | `packages/mcp-servers/vm-management` |
| Local agents | Templates and runtime workflows | `templates/agent-runtime`, `examples/local-agent-runtime` |

## Supported Clients

| Client | Best Use | Quickstart |
| --- | --- | --- |
| OpenClaw | Local homelab agent runtime | [docs/quickstart-openclaw.md](docs/quickstart-openclaw.md) |
| Hermes | Local agent runtime and maintenance assistant | [docs/quickstart-hermes.md](docs/quickstart-hermes.md) |
| Claude | MCP desktop/client operator | [docs/quickstart-claude.md](docs/quickstart-claude.md) |
| Codex | Repo operator for scripts, docs, validation, workflows | [docs/quickstart-codex.md](docs/quickstart-codex.md) |
| Cursor | Coding-agent editing and validation | [docs/quickstart-cursor.md](docs/quickstart-cursor.md) |
| Grok | Planning/reference assistant | [docs/quickstart-grok.md](docs/quickstart-grok.md) |

See [docs/client-compatibility.md](docs/client-compatibility.md).

## Common Commands

```bash
make validate                 # schema checks, repo checks, MCP smoke tests
make guardrail-smoke          # action classification examples
make workflow-chooser-smoke   # workflow recommendations from sample inventory
make release-audit            # pass/fail/manual release evidence
make doctor                   # local readiness checks
```

Generate an MCP client config with absolute paths:

```bash
python3 scripts/generate_mcp_config.py \
  --inventory templates/inventory/homelab.inventory.example.json \
  --output generated/mcp-config.json
```

Create a redacted diagnostics bundle:

```bash
python3 scripts/create_diagnostics_bundle.py \
  --output diagnostics/example \
  --inventory templates/inventory/homelab.inventory.example.yaml
```

## Documentation Map

Start here:

- [docs/quickstart.md](docs/quickstart.md)
- [docs/client-compatibility.md](docs/client-compatibility.md)
- [docs/workflow-chooser.md](docs/workflow-chooser.md)
- [docs/implemented-capabilities.md](docs/implemented-capabilities.md)

Safety and operations:

- [docs/safety-model.md](docs/safety-model.md)
- [docs/action-risk-matrix.md](docs/action-risk-matrix.md)
- [docs/threat-model.md](docs/threat-model.md)
- [docs/credential-patterns.md](docs/credential-patterns.md)
- [docs/maintenance-loop.md](docs/maintenance-loop.md)
- [docs/backup-restore-drills.md](docs/backup-restore-drills.md)

Project and release:

- [docs/repo-map.md](docs/repo-map.md)
- [docs/release-readiness.md](docs/release-readiness.md)
- [docs/roadmap.md](docs/roadmap.md)
- [CHANGELOG.md](CHANGELOG.md)

## Current Status

v0.1 — the reference servers speak real MCP and are smoke-tested against
fixtures in CI; they have not yet been exercised against live Proxmox/Docker
hosts by independent users. The repo includes working read-only reference MCP
servers, machine-readable workflows, schemas, validation, release audit
tooling, guardrails, templates, and client quickstarts.
Repository identity and the skills installer shorthand are declared in
`catalog/index.yaml` under `repository`.

Some checks still require real environments and are intentionally marked manual
by `make release-audit`, including fresh-clone validation by another user, a
real scoped Proxmox token test, Docker host testing, and diagnostics on macOS and
Linux.

See [docs/implemented-capabilities.md](docs/implemented-capabilities.md) for the
exact implementation boundary.

## Contributing

Contributions are welcome when they preserve the safety model.

New integrations should include:

- a package or skill README;
- a read-only mode;
- permission documentation;
- examples;
- safety notes;
- catalog metadata;
- validation coverage where possible.

See [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md),
and [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).

---

⭐ If this saves your homelab from an over-eager agent, a star helps others find it.
