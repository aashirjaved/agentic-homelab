# Agent Lessons From Local Sessions

This document distills recurring friction points from local Claude, Codex, and Pi/OpenClaw/Magzi work. It intentionally avoids copying private transcripts. The goal is to turn repeated pain into repo requirements.

## Core Thesis

Homelab automation is not mainly a scripting problem. It is an agent operations problem.

Agents struggle when they do not know:

- what infrastructure exists,
- which model/runtime path is sanctioned,
- which credentials are safe to use,
- what actions require approval,
- how to verify success externally,
- how to recover after a failed or partial action,
- and which context should persist across future sessions.

`agentic-homelab` should make those things explicit.

## Repeated Friction Points

### 1. Discovery Is Too Ad Hoc

Agents often start by guessing: SSH here, inspect there, search random files, infer topology from conversation. This is fragile.

Repo implication:

- provide inventory schemas for nodes, services, storage, networks, agents, and credentials;
- make read-only discovery the first-class path;
- expose MCP tools that answer "what exists?" before "change this."

### 2. Homelab Mental Models Need Encoding

The same concepts are easy to confuse:

- Tailscale remote access versus outbound privacy VPN;
- backup versus same-node copy;
- NAS bulk storage versus hot database storage;
- public ingress versus tailnet-only access;
- Proxmox host state versus VM/container state.

Repo implication:

- add architecture checklists for common setups;
- teach agents to flag fake backups and hidden single points of failure;
- model inbound, outbound, storage, compute, and backup flows separately.

### 3. Secrets Exist Locally But Are Unsafe Without Context

Agents can find local secrets, SSH strings, tokens, and env files, but using them blindly is risky. A credential may be too broad, stale, or intended only for one machine.

Repo implication:

- define a secrets manifest format that describes purpose, scope, owner, rotation, and allowed tools without storing the secret itself;
- prefer scoped API tokens over root passwords;
- require redaction in logs and summaries;
- classify `credential-access` as approval-gated.

### 4. Root Access Is Too Blunt

Homelabs often begin with `ssh root@node`, because it works. Agents then lack a reliable boundary between inspection and mutation.

Repo implication:

- provide least-privilege setup guides for Proxmox, Docker, NAS, and monitoring;
- create read-only users/tokens where platforms support them;
- document when root is unavoidable;
- require command previews for privileged writes.

### 5. Verification Beats Self-Assessment

A recurring lesson from Magzi/Pi work: an agent saying "done" is not verification. Loops need checks the model cannot fake.

Repo implication:

- every workflow should include an external verifier;
- examples: service health endpoint, Proxmox task status, Docker container health, SMART result, backup restore check, log query, port check, UI smoke test;
- unattended loops must not run unless their success condition can be mechanically checked.

### 6. Failed Background Jobs Need a Safe Shape

Agent jobs can fail with empty model responses, missing permissions, unavailable services, or partial execution. The safe behavior is to fail closed, report clearly, and avoid confirming action.

Repo implication:

- standardize job states: `planned`, `approved`, `running`, `failed-safe`, `verified`, `rolled-back`;
- record the before/after state for changes;
- make failed jobs explain what was not changed;
- require retry plans instead of blind retries.

### 7. Model Routing Must Be Explicit

In the Magzi work, generation had to go through Pi while Ollama was embeddings-only. That kind of routing rule matters in homelabs where some models are local, some remote, and some audited.

Repo implication:

- add a model-routing policy file;
- separate generation, embeddings, vision, reranking, and verification models;
- document privacy and audit expectations for each route;
- let agents inspect the policy before calling any model.

### 8. Memory Needs Source Grounding

Long-running agents need memory, but ungrounded memory can become a liability. Useful memory records the source, timestamp, confidence, and what system it applies to.

Repo implication:

- add memory cards for homelab facts: nodes, services, network, credentials metadata, incidents, decisions, recurring tasks;
- require provenance for persistent facts;
- distinguish observed state from user preference from agent inference;
- support expiration for facts likely to go stale.

### 9. Local-First Agents Need Runtime Operations

OpenClaw, Hermes, Magzi, Codex-like agents, and browser/MCP workers all become part of the homelab. They need the same operational treatment as any other service.

Repo implication:

- include agent runtime inventory;
- document service files, logs, health checks, restart policy, model dependencies, and tool permissions;
- provide a skill for agent self-management that starts read-only and requires approval for restarts or credential changes.

### 10. Tool Choice Depends On Execution Context

A coding agent with shell access can install and run a CLI. A chat-only UI may need MCP. A local daemon may need a long-lived service. The repo should not assume one interface.

Repo implication:

- for each capability, document CLI, MCP, and manual fallback paths;
- skills should first detect their environment;
- MCP servers should expose the same conceptual operations as CLI examples.

### 11. Logs Must Be Easy To Package

Several sessions turned into "check logs, explain what failed, verify it now." Users need a one-command support bundle an agent can inspect or share.

Repo implication:

- define a homelab diagnostics bundle format;
- include logs, versions, service status, recent tasks, config fingerprints, and redacted env metadata;
- never include raw secrets.

### 12. Product Docs Must Be Scannable

Repeated repo work showed that wall-of-text READMEs slow adoption. Users need a visual path: what this solves, where to start, what is safe, and what to install.

Repo implication:

- keep the README high-signal;
- use catalog metadata for machines;
- put deep safety and implementation notes in docs;
- make examples copyable.

## Main Requirements For This Repo

1. Read-only inventory before mutation.
2. Explicit safety classification for every tool.
3. Scoped credentials and redaction by default.
4. Human approval for writes, power operations, storage changes, firewall changes, and credential access.
5. Mechanical verification for every workflow.
6. Durable memory with source grounding and staleness handling.
7. Model-routing policy for local, remote, embeddings, vision, and verifier calls.
8. Agent runtime management as a first-class homelab domain.
9. CLI, MCP, and manual paths for major capabilities.
10. Practical examples for Proxmox, Docker, NAS, monitoring, remote access, and local agents.

## First Workflows To Build

- `homelab.inventory.readonly` - discover nodes, services, storage, network, and agent runtimes.
- `proxmox.node.health` - list nodes, guests, storage, tasks, and warnings.
- `docker.stack.health` - inspect Compose stacks, health checks, image age, volumes, and restart policy.
- `storage.backup.reality-check` - distinguish same-node copies from real 3-2-1 backups.
- `network.remote-access.review` - classify Tailscale, VPN, ingress, exposed ports, and outbound privacy.
- `agent.runtime.audit` - inspect local agents, model routes, permissions, logs, and restart policy.
- `diagnostics.bundle.create` - collect redacted, shareable support context.

## Agent Operating Defaults

- Start by saying what will be inspected.
- Never print secrets.
- Prefer platform APIs over shell where available.
- Treat unknown tools as write-risk until classified.
- Do not restart, delete, power off, reformat, expose ports, or rotate credentials without approval.
- Verify with an external signal, not the agent's own judgment.
- Leave behind a short change record.

