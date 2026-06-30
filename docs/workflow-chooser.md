# Workflow Chooser

Use this when you have an inventory but are unsure where to start.

```bash
python3 scripts/choose_workflow.py --inventory homelab.inventory.yaml
```

The chooser reads only the inventory file and recommends example workflows. It
does not contact your homelab, run MCP tools, or make changes.

## Recommendation Signals

| Inventory Signal | Suggested Workflow |
| --- | --- |
| Proxmox node or Proxmox storage | `examples/proxmox-vm-maintenance/workflow.yaml` |
| Docker host, media services, or ingress services | `examples/docker-stack-maintenance/workflow.yaml` |
| NAS, shares, backup targets, or media storage | `examples/media-server-nas/workflow.yaml` |
| Backup status, unknown backup freshness, or no restore evidence | `examples/backup-restore-drill/workflow.yaml` |
| Local agents, OpenClaw, Hermes, or an agent runtime host | `examples/local-agent-runtime/workflow.yaml` |
| Multiple nodes, network metadata, or service exposure metadata | `examples/multi-node-monitoring/workflow.yaml` |
| Unknown backup status or unclear setup | `examples/diagnostics-bundle/workflow.yaml` |

## Safe First Prompt

```text
Read the recommended workflow and guardrails/policies/default-policy.yaml.
Use only read-only tools. Do not make changes. Return findings, uncertainty,
and the verifier you would use before any future approved change.
```

If several workflows match, pick the one with the smallest blast radius first.
