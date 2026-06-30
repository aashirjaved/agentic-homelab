# Quickstart

This is the shortest safe path from "I have a homelab" to "an agent can help maintain it."

## 1. Create An Inventory

Fastest path: bootstrap a starter homelab context directory.

```bash
python3 scripts/bootstrap_homelab_repo.py /path/to/your/homelab-agent-context
```

This creates an inventory, default policy, action risk matrix, `AGENTS.md`, and
a maintenance log without writing secrets or touching your infrastructure.

Manual path:

Copy the example:

```bash
cp templates/inventory/homelab.inventory.example.yaml homelab.inventory.yaml
```

Fill in nodes, services, storage, networks, and local agents. Do not put secrets in this file. Use `credential_ref` names that point to your password manager, `.env` loader, OS keychain, or agent runtime secret store.

You can also start from a more specific template:

- `templates/inventory/single-node-docker-media.yaml`
- `templates/inventory/proxmox-nas-split.yaml`
- `templates/inventory/local-agent-runtime.yaml`

## 2. Choose A Safety Policy

Start with:

```text
guardrails/policies/default-policy.yaml
```

This policy makes read-only discovery safe and gates writes, destructive actions, firewall changes, and credential access.

If you keep your homelab config in a repository, copy the agent instructions
template into that repo:

```bash
cp templates/agent-instructions/AGENTS.md /path/to/your/homelab/AGENTS.md
```

Replace the placeholder paths so Codex, Claude, Cursor, OpenClaw, Hermes, and
other agents know where inventory, policy, workflows, and diagnostics live.

Run a local preflight:

```bash
python3 scripts/doctor.py --inventory homelab.inventory.yaml
```

Warnings are expected when optional CLIs are not installed. Failures should be fixed before connecting agents.

If you also use Ansible, run the read-only audit before approving any setup work:

```bash
ansible-playbook -i inventory.ini playbooks/ansible/read-only-audit.yml
```

Treat the output as discovery input for an agent, not as approval to remediate.

## 3. Choose One Domain

Pick the smallest useful target:

- Proxmox health
- Docker stack health
- NAS backup reality check
- monitoring alert triage
- local agent runtime audit

Do not enable every tool at once.

You can ask the repo to recommend starter workflows from your inventory:

```bash
python3 scripts/choose_workflow.py --inventory homelab.inventory.yaml
```

See [workflow-chooser.md](workflow-chooser.md) for the mapping.

For Proxmox, see [proxmox-readonly-token.md](proxmox-readonly-token.md) before connecting an agent.

## 4. Run Read-Only Discovery

Recommended first prompt for any agent:

```text
Use the safety harness. Read homelab.inventory.yaml and the default guardrail policy. Inspect only read-only state for <target>. Do not make changes. Produce findings, risks, and the exact verifier you would use before any future change.
```

Generate an MCP client config with absolute paths:

```bash
python3 scripts/generate_mcp_config.py --inventory homelab.inventory.json --output generated/mcp-config.json
```

Then copy the relevant `mcpServers` entries into your client configuration.

## 5. Approve One Change At A Time

Before a write, the agent should show:

- target,
- command or MCP tool,
- expected effect,
- rollback option,
- verification command,
- risk level.

## 6. Record Results

After maintenance, keep a short note:

```text
Time:
Target:
Action:
Approval:
Verifier:
Result:
Residual risk:
```

## Local Agent Notes

For OpenClaw, Hermes, Magzi, or other self-hosted agents:

- run the agent as a service with logs and health checks;
- keep model routing explicit;
- use read-only tools first;
- require approval for restarts, credentials, and policy changes;
- treat the agent runtime itself as part of the homelab inventory.

System service examples live in `templates/agent-runtime/`.
