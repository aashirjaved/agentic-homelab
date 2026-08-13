# Homelab Doctor

`homelab_doctor.py` is the shortest path from a machine to a useful answer. It
uses bounded read-only Docker inspection, optionally merges YAML or JSON
inventory, builds a dependency graph, identifies obvious risks and missing
knowledge, and makes no infrastructure changes.

```bash
python scripts/homelab_doctor.py
```

Local discovery currently covers Docker containers, images, state, health,
published ports, and mounts; local filesystem capacity; hostname resolution and
Tailscale connection state; and an optional remote Proxmox API. Every source has
an evidence status. Missing CLIs, unreachable daemons, and parse failures are
shown as unavailable or partial—not silently interpreted as an empty, healthy
lab. An optional integration that is not configured is labeled `not-configured`.

### Proxmox discovery

Use a scoped, read-only API token as documented in
[proxmox-readonly-token.md](proxmox-readonly-token.md):

```bash
export PROXMOX_API_URL=https://pve.example:8006
export PROXMOX_API_TOKEN_ID='doctor@pve!readonly'
export PROXMOX_API_TOKEN_SECRET='...'
python scripts/homelab_doctor.py
```

The doctor performs GET requests for nodes, guests, node storage, and the latest
50 cluster tasks. Guests become services that run on Proxmox nodes; storage is
linked to each reporting node; tasks join the unified timeline. Tokens are never
placed in reports or history. TLS verification defaults on and request timeouts
are capped at 30 seconds.

Local filesystem mount paths are deliberately replaced with opaque identifiers
in reports, while capacity remains available for risk detection. A filesystem at
90% or more is flagged as critical. Network discovery records only summarized
resolution and tailnet state, not addresses or peer lists.

### Service and NAS health probes

Any service or storage entry can declare a vendor-neutral HTTP health check:

```yaml
services:
  - id: jellyfin
    kind: media
    healthcheck:
      url_env: JELLYFIN_HEALTH_URL
      expected_status: 200
      timeout_seconds: 5
storage:
  - id: nas
    kind: nas
    healthcheck:
      url: https://nas.internal/health
      expected_status: [200, 204]
```

Use `url_env` when the endpoint itself should not live in inventory. Probes use
GET with a 15-second hard timeout and never store or render URLs, response
bodies, headers, or credentials. URLs containing embedded credentials and
non-HTTP schemes are rejected. Only health state, HTTP status, latency, and a
generic error class enter the observation.

An unhealthy service feeds incident hypotheses; an unhealthy NAS/storage probe
becomes an inactive-storage finding. A completed probe that observes failure is
still valid evidence, so it does not masquerade as an evidence-source outage.

Use `--inventory path/to/homelab.inventory.yaml` to merge declared knowledge.
Declared fields take precedence while live-only fields such as container state
are retained. Use `--no-discover` for a deterministic inventory-only report.

## Incident investigator

```bash
python scripts/homelab_doctor.py \
  --inventory path/to/homelab.inventory.yaml \
  --investigate jellyfin
```

The investigator walks outward through `runs_on`, `uses_storage`, and
`depends_on` relationships. It combines direct service symptoms, findings on
dependencies, unavailable evidence sources, and changes from the current
observation. Each hypothesis includes a confidence label, supporting evidence,
downstream impact, and read-only verification steps.

Confidence is deliberately bounded. A stopped or unhealthy observed dependency
can be “likely”; backup uncertainty and broad network listening are weak signals,
not declared causes. When no relevant evidence exists, the result says
`insufficient-evidence` and recommends additional observation rather than a fix.

## Recovery readiness

The doctor scores recovery per service across six evidence checks:

1. configuration needed to recreate the service;
2. secrets, encryption keys, and recovery codes;
3. an ordered restore runbook;
4. a successful restore test within the last year;
5. backups for every modeled stateful storage dependency;
6. a recoverable copy outside the source failure domain.

Statuses are conservative:

- `proven`: all six checks pass;
- `partial`: at least half pass, with no blocking loss;
- `unproven`: fewer than half pass or the evidence is mostly unknown;
- `unrecoverable`: required data or secrets/keys are explicitly missing.

Unknown is never counted as passing. The percentage is evidence completeness,
not a probability that restoration will succeed.

```yaml
services:
  - id: jellyfin
    kind: media
    uses_storage: [media]
    recovery:
      configuration_status: version-controlled
      secrets_required: false
      restore_runbook: docs/restore-jellyfin.md
      last_restore_test: 2026-07-01T12:00:00Z
storage:
  - id: media
    kind: nas
    backup_status: fresh
    failure_domain: nas-chassis
    backup_failure_domain: offsite
```

The doctor only evaluates declared evidence. It does not open runbook paths or
perform a restore. Restore drills remain separately approved operations.

## Update intelligence

```bash
python scripts/homelab_doctor.py --plan-updates
python scripts/homelab_doctor.py --plan-updates jellyfin
```

Update intelligence evaluates a candidate without pulling an image or restarting
a service. Its gates cover current health, recovery readiness, authoritative
release-note review, breaking-change review, rollback, independent verification,
recent stability, and graph-derived blast radius.

Decisions mean:

- `ready-for-approval`: every gate passes; this is still not authorization;
- `caution`: no blocker is proven, but required evidence remains unknown;
- `blocked`: a health, recovery, research, or rollback blocker is explicit;
- `no-candidate`: no target update is declared or observed.

```yaml
update:
  available: true
  current_version: 10.10.6
  target_version: 10.10.7
  release_notes_reviewed: true
  breaking_changes_reviewed: true
  rollback: pin image to 10.10.6
  verification:
    - container is healthy
    - web endpoint returns 200
```

The ordered output is a research and approval plan. No update command is run.

## Relationship fields

The existing inventory fields form the first version of the Homelab Graph:

| Field | Relationship |
| --- | --- |
| `services[].runs_on` | service → node |
| `services[].uses_storage[]` | service → storage |
| `services[].depends_on[]` | service → service or other component |
| `storage[].mounted_by[]` | node → storage |

The doctor currently detects missing relationship targets, public exposure,
unproven recovery status, and shared dependencies. It also reports questions
that cannot be answered from the supplied evidence, including missing change
history and restore-test evidence. This distinction is deliberate: unknown is
not healthy.

## Machine-readable output

Use `--format json` for agents, scripts, or future ingestion:

```bash
python scripts/homelab_doctor.py \
  --inventory path/to/homelab.inventory.yaml \
  --format json
```

The output contains `summary`, `relationships`, `findings`, `unknowns`, and a
`read_only: true` assertion. Findings include severity, a stable code, subject,
summary, and recommended next step. `timeline` contains timestamped semantic
events across observed nodes, services, storage, image versions, runtime health,
exposure, recovery status, and dependency fields.

## What changed

By default, the doctor records a bounded 30-observation history in
`.agentic-homelab/history.json`. The first run establishes a baseline. Later runs
report additions, removals, and meaningful field changes; changing uptime text
is deliberately ignored to avoid noise.

History contains only selected topology and diagnostic fields. Access blocks,
addresses, credential references, environment variables, and raw logs are never
persisted. Use `--history path/to/history.json` to choose another location or
`--no-history` for an ephemeral run.

## Shareable diagnostics

`--share report.md` writes a Markdown copy with private IPv4 addresses and URL
hosts redacted. The terminal still receives the normal unredacted report so the
operator can diagnose locally.

Redaction reduces accidental disclosure; it is not a promise that arbitrary
free-form inventory notes are safe. Review every report before sharing it.

Use `--bundle path/to/empty-directory` for a self-contained support artifact.
It contains:

- `report.md`: human-readable diagnosis;
- `report.json`: the same derived evidence for tools;
- `manifest.json`: format, generator, file list, and exclusions;
- `README.md`: disclosure and review guidance.

The bundle excludes raw inventory, environment values, credentials, endpoint
URLs and bodies, logs, and raw command output. It refuses to write into a
non-empty directory so an existing diagnostic artifact is never overwritten.

## Current boundary

This doctor release observes local Docker, host storage and network signals, and
configured Proxmox. It does not yet speak vendor NAS APIs or prove end-to-end
service health. Its evidence section makes those boundaries visible. Additional
read-only sources should enrich the same graph and findings model rather than
create disconnected reports.
