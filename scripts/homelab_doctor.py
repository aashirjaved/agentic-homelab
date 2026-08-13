#!/usr/bin/env python3
"""Explain a homelab inventory without changing anything."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import difflib
import json
import os
import platform
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
import ssl

import yaml


PRIVATE_VALUE = re.compile(
    r"(?i)(?:\b(?:10|127)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|"
    r"\b192\.168\.\d{1,3}\.\d{1,3}\b|"
    r"\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b|"
    r"https?://[^\s/]+)"
)
HOME_PATH = re.compile(r"(/(?:Users|home)/)[^/\s]+")


@dataclass(frozen=True)
class Edge:
    source: str
    relation: str
    target: str


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    subject: str
    summary: str
    recommendation: str


HISTORY_VERSION = 1
HISTORY_LIMIT = 30
DEFAULT_HISTORY = Path(".agentic-homelab/history.json")
CHANGE_HISTORY_UNKNOWN = "No change history is connected, so 'what changed?' cannot yet be answered."
SNAPSHOT_FIELDS = {
    "nodes": ("role", "hostname", "platform"),
    "services": ("kind", "runs_on", "image", "state", "health", "exposure", "ports", "uses_storage", "depends_on"),
    "storage": ("kind", "backup_status", "mounted_by"),
}


def run_readonly(command: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Run a bounded, explicitly read-only discovery command."""
    try:
        proc = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 126, "", str(exc)


def docker_discovery(runner=run_readonly) -> tuple[dict[str, Any], dict[str, Any]]:
    docker = shutil.which("docker")
    if not docker:
        return {}, {"source": "docker", "status": "unavailable", "detail": "docker CLI not found"}
    code, stdout, stderr = runner([docker, "ps", "--all", "--format", "{{json .}}"])
    if code != 0:
        detail = stderr.strip() or "docker daemon did not answer"
        return {}, {"source": "docker", "status": "unavailable", "detail": detail[:300]}

    host_id = "local-host"
    services: list[dict[str, Any]] = []
    storage_by_id: dict[str, dict[str, Any]] = {}
    parse_errors = 0
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        name = str(row.get("Names") or row.get("ID") or "unknown-container")
        ports = str(row.get("Ports", ""))
        service: dict[str, Any] = {
            "id": name,
            "kind": "docker-container",
            "runs_on": host_id,
            "image": str(row.get("Image", "unknown")),
            "observed_status": str(row.get("Status", "unknown")),
            "exposure": "all-interfaces" if re.search(r"(?:0\.0\.0\.0|\[::\]|:::)", ports) else "local-or-unpublished",
            "ports": ports,
            "source": "docker",
        }
        services.append(service)

    if services:
        ids = [service["id"] for service in services]
        inspect_code, inspect_stdout, _ = runner([docker, "inspect", *ids])
        if inspect_code == 0:
            try:
                inspected = json.loads(inspect_stdout)
            except json.JSONDecodeError:
                inspected = []
                parse_errors += 1
            service_by_id = {service["id"]: service for service in services}
            for container in inspected if isinstance(inspected, list) else []:
                name = str(container.get("Name", "")).lstrip("/")
                service = service_by_id.get(name)
                if not service:
                    continue
                state = container.get("State", {})
                service["state"] = state.get("Status", "unknown")
                service["health"] = state.get("Health", {}).get("Status", "not-configured")
                uses_storage: list[str] = []
                for mount in container.get("Mounts", []):
                    source = str(mount.get("Name") or mount.get("Source") or "unknown-mount")
                    storage_id = "volume:" + Path(source).name
                    uses_storage.append(storage_id)
                    storage_by_id.setdefault(storage_id, {
                        "id": storage_id,
                        "kind": str(mount.get("Type", "docker-volume")),
                        "mounted_by": [host_id],
                        "backup_status": "unknown",
                        "source": "docker",
                    })
                service["uses_storage"] = sorted(set(uses_storage))

    detail = f"observed {len(services)} containers and {len(storage_by_id)} mounts"
    if parse_errors:
        detail += f"; {parse_errors} responses could not be parsed"
    return {
        "nodes": [{"id": host_id, "role": "docker-host", "hostname": platform.node(), "source": "local"}],
        "services": services,
        "storage": list(storage_by_id.values()),
    }, {"source": "docker", "status": "ok" if not parse_errors else "partial", "detail": detail}


def proxmox_get(path: str) -> dict[str, Any]:
    base = os.environ["PROXMOX_API_URL"].rstrip("/")
    token_id = os.environ["PROXMOX_API_TOKEN_ID"]
    secret = os.environ["PROXMOX_API_TOKEN_SECRET"]
    verify = os.environ.get("PROXMOX_VERIFY_TLS", "true").lower() not in {"0", "false", "no"}
    context = None if verify else ssl._create_unverified_context()
    request = Request(f"{base}/api2/json{path}",
        headers={"Authorization": f"PVEAPIToken={token_id}={secret}"}, method="GET")
    with urlopen(request, timeout=min(int(os.environ.get("PROXMOX_API_TIMEOUT_SECONDS", "10")), 30), context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def api_rows(getter, path: str) -> list[dict[str, Any]]:
    response = getter(path)
    rows = response.get("data")
    if not isinstance(rows, list):
        raise ValueError(f"Proxmox response for {path} did not contain a data list")
    return [row for row in rows if isinstance(row, dict)]


def proxmox_discovery(getter=proxmox_get) -> tuple[dict[str, Any], dict[str, Any]]:
    required = ("PROXMOX_API_URL", "PROXMOX_API_TOKEN_ID", "PROXMOX_API_TOKEN_SECRET")
    if not all(os.environ.get(name) for name in required):
        return {}, {"source": "proxmox", "status": "not-configured", "detail": "read-only API token environment is not configured"}
    try:
        node_rows = api_rows(getter, "/nodes")
        guest_rows = api_rows(getter, "/cluster/resources?type=vm")
        task_rows = api_rows(getter, "/cluster/tasks?limit=50")
        storage_rows: list[dict[str, Any]] = []
        for node in node_rows:
            node_id = str(node.get("node", "unknown-node"))
            for storage in api_rows(getter, f"/nodes/{node_id}/storage"):
                storage_rows.append({**storage, "node": node_id})
    except (HTTPError, URLError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return {}, {"source": "proxmox", "status": "unavailable", "detail": str(exc)[:300]}

    nodes = [{"id": str(row.get("node", "unknown-node")), "role": "proxmox",
              "state": str(row.get("status", "unknown")), "source": "proxmox"} for row in node_rows]
    services = []
    for row in guest_rows:
        guest_id = str(row.get("name") or f"{row.get('type', 'guest')}-{row.get('vmid', 'unknown')}")
        services.append({"id": guest_id, "kind": f"proxmox-{row.get('type', 'guest')}",
            "runs_on": str(row.get("node", "unknown-node")), "state": str(row.get("status", "unknown")),
            "vmid": row.get("vmid"), "source": "proxmox"})
    storage: dict[str, dict[str, Any]] = {}
    for row in storage_rows:
        storage_id = "pve-storage:" + str(row.get("storage", "unknown"))
        item = storage.setdefault(storage_id, {"id": storage_id, "kind": str(row.get("type", "proxmox-storage")),
            "mounted_by": [], "backup_status": "unknown", "source": "proxmox"})
        item["mounted_by"].append(str(row["node"]))
        item["state"] = "active" if row.get("active") in {1, True} else "inactive"
    guest_names = {str(row.get("vmid")): str(row.get("name") or f"{row.get('type', 'guest')}-{row.get('vmid')}")
                   for row in guest_rows if row.get("vmid") is not None}
    changes = [{"source": "proxmox", "subject": guest_names.get(str(row.get("id") or row.get("vmid")),
                str(row.get("id") or row.get("vmid") or row.get("node", "cluster"))),
                "type": str(row.get("type", "task")), "status": str(row.get("status", "unknown")),
                "timestamp": row.get("endtime") or row.get("starttime")} for row in task_rows]
    return {"nodes": nodes, "services": services, "storage": list(storage.values()), "changes": changes}, {
        "source": "proxmox", "status": "ok",
        "detail": f"observed {len(nodes)} nodes, {len(services)} guests, {len(storage)} storage systems, and {len(changes)} recent tasks"}


def host_storage_discovery(runner=run_readonly) -> tuple[dict[str, Any], dict[str, Any]]:
    code, stdout, stderr = runner(["df", "-Pk"])
    if code != 0:
        return {}, {"source": "host-storage", "status": "unavailable", "detail": (stderr.strip() or "df failed")[:300]}
    stores = []
    for index, line in enumerate(stdout.splitlines()[1:]):
        fields = line.split()
        if len(fields) < 6 or fields[0].startswith(("devfs", "map", "tmpfs")):
            continue
        try:
            capacity = int(fields[4].rstrip("%"))
        except ValueError:
            continue
        stores.append({"id": f"local-filesystem:{index + 1}", "kind": "local-filesystem", "mounted_by": ["local-host"],
                       "capacity_percent": capacity, "recovery_relevant": False, "source": "host-storage"})
    return {"storage": stores}, {"source": "host-storage", "status": "ok", "detail": f"observed {len(stores)} local filesystems"}


def network_discovery(runner=run_readonly) -> tuple[dict[str, Any], dict[str, Any]]:
    hostname = platform.node()
    resolved = False
    try:
        import socket
        resolved = bool(socket.getaddrinfo(hostname, None))
    except OSError:
        pass
    tailnet = "unknown"
    tailscale = shutil.which("tailscale")
    if tailscale:
        code, stdout, _ = runner([tailscale, "status", "--json"])
        if code == 0:
            try:
                tailnet = "connected" if json.loads(stdout).get("BackendState") == "Running" else "disconnected"
            except json.JSONDecodeError:
                tailnet = "unknown"
    status = "ok" if resolved else "partial"
    return {"networks": {"local": {"hostname_resolves": resolved, "tailnet": tailnet}}}, {
        "source": "network", "status": status, "detail": f"hostname resolution={'ok' if resolved else 'failed'}; tailnet={tailnet}"}


def http_probe(url: str, timeout: int) -> int:
    request = Request(url, headers={"User-Agent": "agentic-homelab-doctor/1"}, method="GET")
    with urlopen(request, timeout=min(max(timeout, 1), 15)) as response:
        return int(response.status)


def resolve_probe_url(config: dict[str, Any]) -> str | None:
    if isinstance(config.get("url"), str):
        return config["url"]
    env_name = config.get("url_env")
    return os.environ.get(env_name) if isinstance(env_name, str) else None


def endpoint_discovery(inventory: dict[str, Any], probe=http_probe) -> tuple[dict[str, Any], dict[str, Any]]:
    observed: dict[str, list[dict[str, Any]]] = {"services": [], "storage": []}
    attempted = healthy = failed = skipped = 0
    for group in ("services", "storage"):
        for component in inventory.get(group, []):
            config = component.get("healthcheck")
            if not isinstance(config, dict):
                continue
            url = resolve_probe_url(config)
            if not url:
                skipped += 1
                continue
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                skipped += 1
                continue
            attempted += 1
            expected = config.get("expected_status", 200)
            expected_codes = {expected} if isinstance(expected, int) else set(expected) if isinstance(expected, list) else {200}
            started = time.monotonic()
            try:
                status_code = probe(url, int(config.get("timeout_seconds", 5)))
                ok = status_code in expected_codes
                error = None
            except HTTPError as exc:
                status_code, ok, error = exc.code, exc.code in expected_codes, None
            except (URLError, OSError, TimeoutError, ValueError) as exc:
                status_code, ok, error = None, False, type(exc).__name__
            latency_ms = round((time.monotonic() - started) * 1000)
            item = {"id": item_id(component), "probe_status": "healthy" if ok else "unhealthy",
                    "probe_http_status": status_code, "probe_latency_ms": latency_ms, "source": "endpoint-probe"}
            if error:
                item["probe_error"] = error
            if group == "services":
                item["health"] = "healthy" if ok else "unhealthy"
            else:
                item["state"] = "active" if ok else "inactive"
            observed[group].append(item)
            healthy += int(ok)
            failed += int(not ok)
    status = "not-configured" if attempted == 0 and skipped == 0 else "partial" if skipped else "ok"
    detail = f"probed {attempted} endpoints: {healthy} healthy, {failed} unhealthy; {skipped} invalid or unresolved"
    return observed, {"source": "endpoint-probes", "status": status, "detail": detail}


def merge_observations(inventory: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    merged = dict(inventory)
    for group in ("nodes", "services", "storage"):
        updates = {item_id(item): item for item in observed.get(group, [])}
        merged[group] = [{**item, **updates.get(item_id(item), {})} for item in inventory.get(group, [])]
    return merged


def merge_inventory(declared: dict[str, Any], discovered: dict[str, Any]) -> dict[str, Any]:
    merged = dict(declared)
    merged.setdefault("homelab", {"name": platform.node() or "local homelab"})
    for group in ("nodes", "services", "storage"):
        by_id = {item_id(item): dict(item) for item in discovered.get(group, [])}
        for item in declared.get(group, []):
            existing = by_id.get(item_id(item), {})
            existing.update(item)
            by_id[item_id(item)] = existing
        merged[group] = sorted(by_id.values(), key=item_id)
    merged["changes"] = [*discovered.get("changes", []), *declared.get("changes", [])]
    merged["networks"] = {**discovered.get("networks", {}), **declared.get("networks", {})}
    return merged


def discover_local(runner=run_readonly) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    docker_inventory, docker_evidence = docker_discovery(runner)
    proxmox_inventory, proxmox_evidence = proxmox_discovery()
    storage_inventory, storage_evidence = host_storage_discovery(runner)
    network_inventory, network_evidence = network_discovery(runner)
    discovered = merge_inventory({}, docker_inventory)
    discovered = merge_inventory(discovered, proxmox_inventory)
    discovered = merge_inventory(discovered, storage_inventory)
    discovered = merge_inventory(discovered, network_inventory)
    if not any(item_id(node) == "local-host" for node in discovered.get("nodes", [])):
        discovered.setdefault("nodes", []).append({
            "id": "local-host", "role": "host", "hostname": platform.node(),
            "platform": platform.system().lower(), "source": "local",
        })
    evidence = [
        {"source": "local-host", "status": "ok", "detail": f"observed {platform.node() or 'local machine'}"},
        docker_evidence,
        proxmox_evidence,
        storage_evidence,
        network_evidence,
    ]
    return discovered, evidence


def load_inventory(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError("inventory must contain an object")
    return data


def make_snapshot(inventory: dict[str, Any], observed_at: str) -> dict[str, Any]:
    """Keep only diagnostic topology/state fields; never persist access or credential data."""
    components: dict[str, dict[str, dict[str, Any]]] = {}
    for group, fields in SNAPSHOT_FIELDS.items():
        components[group] = {}
        for item in inventory.get(group, []):
            component = {field: item[field] for field in fields if field in item}
            components[group][item_id(item)] = component
    return {"observed_at": observed_at, "components": components}


def load_history(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": HISTORY_VERSION, "snapshots": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"version": HISTORY_VERSION, "snapshots": [], "load_error": str(exc)}
    if data.get("version") != HISTORY_VERSION or not isinstance(data.get("snapshots"), list):
        return {"version": HISTORY_VERSION, "snapshots": [], "load_error": "unsupported history format"}
    return data


def change_severity(group: str, field: str, after: Any) -> str:
    if field in {"state", "health"} and str(after).lower() not in {"running", "healthy", "not-configured"}:
        return "high"
    if field in {"image", "exposure", "backup_status", "runs_on"}:
        return "medium"
    return "info"


def compare_snapshots(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    timestamp = after["observed_at"]
    for group in SNAPSHOT_FIELDS:
        old = before.get("components", {}).get(group, {})
        new = after.get("components", {}).get(group, {})
        for subject in sorted(new.keys() - old.keys()):
            events.append({"at": timestamp, "severity": "info", "category": group,
                "subject": subject, "change": "added", "before": None, "after": new[subject]})
        for subject in sorted(old.keys() - new.keys()):
            events.append({"at": timestamp, "severity": "medium", "category": group,
                "subject": subject, "change": "removed", "before": old[subject], "after": None})
        for subject in sorted(old.keys() & new.keys()):
            fields = sorted(set(old[subject]) | set(new[subject]))
            for field in fields:
                if old[subject].get(field) != new[subject].get(field):
                    events.append({"at": timestamp, "severity": change_severity(group, field, new[subject].get(field)),
                        "category": group, "subject": subject, "change": field,
                        "before": old[subject].get(field), "after": new[subject].get(field)})
    return events


def build_timeline(history: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    snapshots = [*history.get("snapshots", []), current]
    events: list[dict[str, Any]] = []
    for before, after in zip(snapshots, snapshots[1:]):
        events.extend(compare_snapshots(before, after))
    return {
        "status": "baseline" if len(snapshots) == 1 else "tracked",
        "previous_observed_at": snapshots[-2]["observed_at"] if len(snapshots) > 1 else None,
        "snapshot_count": len(snapshots),
        "events": events[-100:],
        "history_error": history.get("load_error"),
    }


def save_history(path: Path, history: dict[str, Any], current: dict[str, Any], limit: int = HISTORY_LIMIT) -> None:
    snapshots = [*history.get("snapshots", []), current][-limit:]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps({"version": HISTORY_VERSION, "snapshots": snapshots}, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def attach_timeline(report: dict[str, Any], timeline: dict[str, Any]) -> None:
    report["timeline"] = timeline
    if CHANGE_HISTORY_UNKNOWN in report["unknowns"]:
        report["unknowns"].remove(CHANGE_HISTORY_UNKNOWN)
    if timeline["status"] == "baseline":
        report["unknowns"].append("Change baseline recorded; run the doctor again to detect what changed.")
    if timeline.get("history_error"):
        report["unknowns"].append(f"Previous change history could not be read: {timeline['history_error']}")
    report["unknowns"] = sorted(set(report["unknowns"]))
    report["summary"]["unknowns"] = len(report["unknowns"])


def attach_external_changes(report: dict[str, Any], changes: list[dict[str, Any]]) -> None:
    if not changes:
        return
    timeline = report.setdefault("timeline", {"status": "tracked", "previous_observed_at": None,
        "snapshot_count": 0, "events": [], "history_error": None})
    for change in changes:
        raw_time = change.get("timestamp")
        if isinstance(raw_time, (int, float)):
            at = datetime.fromtimestamp(raw_time, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            at = str(raw_time or report["observed_at"])
        status = str(change.get("status", "unknown"))
        timeline["events"].append({"at": at, "severity": "high" if status.lower() not in {"ok", "unknown"} else "info",
            "category": change.get("source", "external"), "subject": str(change.get("subject", "unknown")),
            "change": str(change.get("type", "event")), "before": None, "after": status})
    timeline["events"].sort(key=lambda event: event["at"])


def item_id(item: dict[str, Any]) -> str:
    return str(item.get("id", "unknown"))


def build_edges(inventory: dict[str, Any]) -> list[Edge]:
    edges: list[Edge] = []
    for service in inventory.get("services", []):
        if service.get("runs_on"):
            edges.append(Edge(item_id(service), "runs_on", str(service["runs_on"])))
        for storage_id in service.get("uses_storage", []):
            edges.append(Edge(item_id(service), "uses", str(storage_id)))
        for dependency in service.get("depends_on", []):
            edges.append(Edge(item_id(service), "depends_on", str(dependency)))
    for storage in inventory.get("storage", []):
        for node_id in storage.get("mounted_by", []):
            edges.append(Edge(str(node_id), "mounts", item_id(storage)))
    return sorted(set(edges), key=lambda edge: (edge.source, edge.relation, edge.target))


def analyze(inventory: dict[str, Any], edges: list[Edge]) -> tuple[list[Finding], list[str]]:
    nodes = inventory.get("nodes", [])
    services = inventory.get("services", [])
    storage = inventory.get("storage", [])
    known = {item_id(item) for group in (nodes, services, storage) for item in group}
    findings: list[Finding] = []
    unknowns: list[str] = []

    for edge in edges:
        if edge.target not in known:
            findings.append(Finding("high", "missing-dependency", edge.source,
                f"References {edge.target!r}, which is absent from inventory.",
                "Add the missing component or correct the relationship."))

    for service in services:
        service_id = item_id(service)
        if not service.get("runs_on"):
            unknowns.append(f"Where does service {service_id} run?")
        exposure = str(service.get("exposure", "unknown")).lower()
        if exposure == "unknown":
            unknowns.append(f"How is service {service_id} exposed?")
        elif exposure in {"public", "public-internet", "internet", "publicly-exposed"}:
            findings.append(Finding("high", "public-service", service_id,
                "Service is marked as publicly exposed.",
                "Verify authentication, TLS, patch level, and whether public ingress is necessary."))
        elif exposure == "all-interfaces":
            findings.append(Finding("medium", "broad-listen", service_id,
                "A published container port listens on all host interfaces; internet reachability is not yet established.",
                "Verify firewall, router, reverse-proxy, and VPN paths before treating this as private."))
        state = str(service.get("state", "")).lower()
        health = str(service.get("health", "")).lower()
        if state and state != "running":
            findings.append(Finding("high", "service-not-running", service_id,
                f"Container state is {state}.", "Inspect recent logs and the dependency graph before restarting it."))
        if health == "unhealthy":
            findings.append(Finding("high", "service-unhealthy", service_id,
                "Container health check reports unhealthy.", "Inspect the health-check output, logs, and dependencies."))

    for store in storage:
        store_id = item_id(store)
        backup = str(store.get("backup_status", "unknown")).lower()
        if store.get("recovery_relevant", True) and backup in {"unknown", "none", "missing", "stale", "failed", "unverified"}:
            severity = "high" if backup in {"none", "missing", "failed"} else "medium"
            findings.append(Finding(severity, "recovery-unproven", store_id,
                f"Recovery status is {backup}; a successful backup job alone does not prove recovery.",
                "Record backup location, required keys/configuration, and the last tested restore."))
        if not store.get("mounted_by"):
            unknowns.append(f"Which nodes mount storage {store_id}?")
        if store.get("state") == "inactive":
            findings.append(Finding("high", "storage-inactive", store_id,
                "Storage is reported inactive.", "Verify the storage path and upstream dependencies before restarting consumers."))
        capacity = store.get("capacity_percent")
        if isinstance(capacity, int) and capacity >= 90:
            findings.append(Finding("high", "storage-capacity-critical", store_id,
                f"Filesystem is {capacity}% full.", "Identify growth and reclaim or expand capacity with a separately approved plan."))

    dependants = Counter(edge.target for edge in edges)
    for target, count in sorted(dependants.items()):
        if count >= 2:
            findings.append(Finding("medium", "shared-dependency", target,
                f"{count} inventoried components depend on this component.",
                "Confirm monitoring, recovery, and an independent access path before maintenance."))

    if not inventory.get("changes"):
        unknowns.append(CHANGE_HISTORY_UNKNOWN)
    if not inventory.get("restore_tests"):
        unknowns.append("No restore-test evidence is recorded.")

    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda finding: (rank.get(finding.severity, 9), finding.code, finding.subject))
    return findings, sorted(set(unknowns))


def inspect_inventory(inventory: dict[str, Any], evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    edges = build_edges(inventory)
    findings, unknowns = analyze(inventory, edges)
    source_evidence = evidence or [{"source": "inventory", "status": "declared", "detail": "not live-verified"}]
    for item in source_evidence:
        if item["status"] in {"unavailable", "partial"}:
            severity = "medium" if item["status"] == "unavailable" else "low"
            findings.append(asdict(Finding(severity, "evidence-gap", item["source"],
                f"Discovery source is {item['status']}: {item['detail']}",
                "Restore this read-only source, then run the doctor again before drawing conclusions.")))
    findings = [asdict(finding) if isinstance(finding, Finding) else finding for finding in findings]
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda finding: (rank.get(finding["severity"], 9), finding["code"], finding["subject"]))
    return {
        "homelab": str(inventory.get("homelab", {}).get("name", "unnamed homelab")),
        "summary": {
            "nodes": len(inventory.get("nodes", [])),
            "services": len(inventory.get("services", [])),
            "storage": len(inventory.get("storage", [])),
            "relationships": len(edges),
            "risks": len(findings),
            "unknowns": len(unknowns),
        },
        "relationships": [asdict(edge) for edge in edges],
        "findings": findings,
        "unknowns": unknowns,
        "evidence": source_evidence,
        "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "read_only": True,
    }


def declared_state(value: Any, passing: set[str], failing: set[str]) -> str:
    normalized = str(value if value is not None else "unknown").strip().lower()
    if normalized in passing:
        return "pass"
    if normalized in failing:
        return "fail"
    return "unknown"


def known_value(value: Any) -> bool:
    return str(value if value is not None else "").strip().lower() not in {"", "unknown", "unset", "none", "missing"}


def recent_restore_test(value: Any, max_age_days: int = 365) -> tuple[str, str]:
    normalized = str(value if value is not None else "unknown").strip()
    if normalized.lower() in {"", "unknown", "never", "missing", "none"}:
        return "unknown" if normalized.lower() in {"", "unknown"} else "fail", normalized or "unknown"
    try:
        tested_at = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        if tested_at.tzinfo is None:
            tested_at = tested_at.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - tested_at).days
    except ValueError:
        return "unknown", f"unparseable timestamp: {normalized}"
    return ("pass", f"{age_days} days ago") if age_days <= max_age_days else ("fail", f"stale: {age_days} days ago")


def readiness_check(name: str, state: str, evidence: str, action: str, blocking: bool = False) -> dict[str, Any]:
    return {"name": name, "state": state, "evidence": evidence, "action": action, "blocking": blocking}


def service_recovery_readiness(service: dict[str, Any], inventory: dict[str, Any], edges: list[dict[str, str]]) -> dict[str, Any]:
    service_id = item_id(service)
    recovery = service.get("recovery", {}) if isinstance(service.get("recovery", {}), dict) else {}
    storage_by_id = {item_id(item): item for item in inventory.get("storage", [])}
    storage_ids = [subject for subject in reachable(service_id, edges) if subject in storage_by_id]
    checks: list[dict[str, Any]] = []

    config_state = declared_state(recovery.get("configuration_status"),
        {"verified", "backed-up", "version-controlled", "present"}, {"missing", "none", "lost"})
    checks.append(readiness_check("configuration", config_state,
        str(recovery.get("configuration_status", "unknown")),
        "Back up and version the configuration required to recreate this service."))

    if recovery.get("secrets_required") is False:
        secret_state, secret_evidence = "pass", "declared not required"
    else:
        secret_state = declared_state(recovery.get("secrets_status"),
            {"verified", "escrowed", "backed-up", "present"}, {"missing", "none", "lost"})
        secret_evidence = str(recovery.get("secrets_status", "unknown"))
    checks.append(readiness_check("secrets-and-keys", secret_state, secret_evidence,
        "Securely preserve required secrets, encryption keys, and recovery codes.", blocking=secret_state == "fail"))

    runbook = recovery.get("restore_runbook")
    runbook_state = "pass" if isinstance(runbook, str) and runbook.strip() else "fail" if runbook is False else "unknown"
    checks.append(readiness_check("restore-runbook", runbook_state, str(runbook or "unknown"),
        "Document ordered restore steps and their prerequisites."))

    test_state, test_detail = recent_restore_test(recovery.get("last_restore_test"))
    checks.append(readiness_check("restore-test", test_state, test_detail,
        "Run a separately approved restore drill into a non-production destination."))

    if recovery.get("data_required") is False:
        data_state, data_evidence, data_blocking = "pass", "declared stateless", False
    elif not storage_ids:
        data_state, data_evidence, data_blocking = "unknown", "no storage dependency modeled", False
    else:
        states = [declared_state(storage_by_id[storage_id].get("backup_status"),
            {"verified", "tested", "fresh", "healthy", "restorable"},
            {"none", "missing", "failed", "lost"}) for storage_id in storage_ids]
        data_state = "pass" if all(state == "pass" for state in states) else "fail" if any(state == "fail" for state in states) else "unknown"
        data_evidence = ", ".join(f"{storage_id}={storage_by_id[storage_id].get('backup_status', 'unknown')}" for storage_id in storage_ids)
        data_blocking = data_state == "fail"
    checks.append(readiness_check("data-backup", data_state, data_evidence,
        "Create a successful backup for every stateful storage dependency.", blocking=data_blocking))

    if recovery.get("data_required") is False:
        domain_state, domain_evidence = "pass", "stateless service"
    elif not storage_ids:
        domain_state, domain_evidence = "unknown", "no storage dependency modeled"
    else:
        domain_states: list[str] = []
        details: list[str] = []
        for storage_id in storage_ids:
            store = storage_by_id[storage_id]
            if store.get("independent_backup") is True:
                domain_states.append("pass")
                details.append(f"{storage_id}=independent")
            elif store.get("independent_backup") is False:
                domain_states.append("fail")
                details.append(f"{storage_id}=same failure domain")
            else:
                source_domain, backup_domain = store.get("failure_domain"), store.get("backup_failure_domain")
                if known_value(source_domain) and known_value(backup_domain):
                    same = source_domain == backup_domain
                    domain_states.append("fail" if same else "pass")
                    details.append(f"{storage_id}={source_domain}→{backup_domain}")
                else:
                    domain_states.append("unknown")
                    details.append(f"{storage_id}=unknown")
        domain_state = "pass" if all(state == "pass" for state in domain_states) else "fail" if any(state == "fail" for state in domain_states) else "unknown"
        domain_evidence = ", ".join(details)
    checks.append(readiness_check("failure-domain-separation", domain_state, domain_evidence,
        "Keep at least one recoverable copy outside the source failure domain."))

    passed = sum(check["state"] == "pass" for check in checks)
    score = round(100 * passed / len(checks))
    if any(check["blocking"] and check["state"] == "fail" for check in checks):
        status = "unrecoverable"
    elif all(check["state"] == "pass" for check in checks):
        status = "proven"
    elif passed >= len(checks) / 2:
        status = "partial"
    else:
        status = "unproven"
    return {
        "service": service_id, "status": status, "score": score, "storage_dependencies": storage_ids,
        "checks": checks, "missing_evidence": [check["name"] for check in checks if check["state"] != "pass"],
        "next_actions": [check["action"] for check in checks if check["state"] != "pass"],
    }


def attach_recovery_readiness(report: dict[str, Any], inventory: dict[str, Any]) -> None:
    services = [service_recovery_readiness(service, inventory, report["relationships"])
                for service in inventory.get("services", [])]
    counts = Counter(service["status"] for service in services)
    report["recovery_readiness"] = {
        "summary": {status: counts.get(status, 0) for status in ("proven", "partial", "unproven", "unrecoverable")},
        "services": services,
        "principle": "A backup is a signal; a recent successful restore is evidence.",
    }
    for service in services:
        if service["status"] == "proven":
            continue
        severity = "high" if service["status"] == "unrecoverable" else "medium"
        code = "service-unrecoverable" if service["status"] == "unrecoverable" else "service-recovery-unproven"
        report["findings"].append(asdict(Finding(severity, code, service["service"],
            f"Recovery readiness is {service['status']} ({service['score']}%); missing: {', '.join(service['missing_evidence'])}.",
            service["next_actions"][0] if service["next_actions"] else "Preserve current recovery evidence.")))
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    report["findings"].sort(key=lambda finding: (rank.get(finding["severity"], 9), finding["code"], finding["subject"]))
    report["summary"]["risks"] = len(report["findings"])


def update_gate(name: str, state: str, evidence: str, action: str, blocking: bool = False) -> dict[str, Any]:
    return {"name": name, "state": state, "evidence": evidence, "action": action, "blocking": blocking}


def plan_service_update(service: dict[str, Any], report: dict[str, Any], recovery: dict[str, Any]) -> dict[str, Any]:
    service_id = item_id(service)
    update = service.get("update", {}) if isinstance(service.get("update", {}), dict) else {}
    target = update.get("target_version")
    available = update.get("available") is True or known_value(target)
    gates: list[dict[str, Any]] = []
    if not available:
        return {"service": service_id, "decision": "no-candidate", "current_version": update.get("current_version") or service.get("image"),
                "target_version": target, "gates": [], "blast_radius": [], "plan": [],
                "reason": "No update candidate is declared or observed."}

    state, health = str(service.get("state", "unknown")).lower(), str(service.get("health", "unknown")).lower()
    health_state = "fail" if state not in {"", "unknown", "running"} or health == "unhealthy" else "pass" if state == "running" else "unknown"
    gates.append(update_gate("current-health", health_state, f"state={state}, health={health}",
        "Resolve current health problems before attributing new failures to an update.", blocking=health_state == "fail"))

    recovery_state = recovery.get("status", "unproven")
    gate_state = "pass" if recovery_state == "proven" else "fail" if recovery_state == "unrecoverable" else "unknown"
    gates.append(update_gate("recovery-readiness", gate_state, f"{recovery_state} ({recovery.get('score', 0)}%)",
        "Gather missing recovery evidence before maintenance.", blocking=recovery_state == "unrecoverable"))

    for field, label, action in (
        ("release_notes_reviewed", "release-notes", "Review authoritative release notes for the exact version transition."),
        ("breaking_changes_reviewed", "breaking-changes", "Review migrations, deprecations, and breaking changes."),
    ):
        value = update.get(field)
        gates.append(update_gate(label, "pass" if value is True else "fail" if value is False else "unknown",
            "reviewed" if value is True else "not reviewed" if value is False else "unknown", action, blocking=value is False))

    rollback = update.get("rollback")
    rollback_state = "pass" if isinstance(rollback, str) and rollback.strip() else "fail" if rollback is False else "unknown"
    gates.append(update_gate("rollback-plan", rollback_state, str(rollback or "unknown"),
        "Document an exact rollback version and restoration path.", blocking=rollback is False))
    verification = update.get("verification") if isinstance(update.get("verification"), list) else []
    gates.append(update_gate("verification-plan", "pass" if verification else "unknown", f"{len(verification)} checks",
        "Define independent health, endpoint, and log verification checks."))

    recent = [event for event in report.get("timeline", {}).get("events", [])
              if event["subject"] == service_id and event["at"] == report["observed_at"]]
    gates.append(update_gate("recent-stability", "unknown" if recent else "pass",
        f"{len(recent)} changes in current observation", "Let recent changes stabilize and verify health before another update."))

    blocked = any(gate["blocking"] and gate["state"] == "fail" for gate in gates)
    unknown = any(gate["state"] == "unknown" for gate in gates)
    decision = "blocked" if blocked else "caution" if unknown else "ready-for-approval"
    blast_radius = reachable(service_id, report["relationships"], reverse=True)
    plan = [
        f"Confirm the intended transition: {update.get('current_version') or service.get('image') or 'unknown'} → {target or 'unknown'}.",
        "Capture current read-only health and dependency evidence.",
        "Request approval for the exact update command; this doctor will not execute it.",
        *[f"Verify: {check}" for check in verification],
        f"If verification fails, use rollback plan: {rollback or 'not yet documented'}.",
    ]
    return {"service": service_id, "decision": decision, "current_version": update.get("current_version") or service.get("image"),
            "target_version": target, "gates": gates, "blast_radius": blast_radius, "plan": plan,
            "reason": "Approval is still required; readiness is not authorization."}


def attach_update_intelligence(report: dict[str, Any], inventory: dict[str, Any], requested: str | None = None) -> None:
    recovery = {item["service"]: item for item in report["recovery_readiness"]["services"]}
    services = inventory.get("services", [])
    if requested:
        services = [service for service in services if item_id(service).casefold() == requested.casefold()]
    plans = [plan_service_update(service, report, recovery.get(item_id(service), {})) for service in services]
    priority = {"ready-for-approval": 0, "caution": 1, "blocked": 2, "no-candidate": 3}
    plans.sort(key=lambda plan: (priority[plan["decision"]], len(plan["blast_radius"]), plan["service"]))
    report["update_intelligence"] = {
        "requested": requested, "plans": plans,
        "summary": dict(Counter(plan["decision"] for plan in plans)),
        "read_only": True,
        "principle": "Update intelligence prepares a decision; it never pulls, restarts, or applies changes.",
    }


def reachable(start: str, edges: list[dict[str, str]], reverse: bool = False) -> list[str]:
    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        source, target = (edge["target"], edge["source"]) if reverse else (edge["source"], edge["target"])
        adjacency.setdefault(source, set()).add(target)
    seen: set[str] = set()
    pending = list(adjacency.get(start, set()))
    while pending:
        subject = pending.pop()
        if subject in seen or subject == start:
            continue
        seen.add(subject)
        pending.extend(adjacency.get(subject, set()) - seen)
    return sorted(seen)


def verification_for(code: str, subject: str) -> list[str]:
    plans = {
        "service-not-running": [f"Read recent logs for {subject}.", "Verify each dependency is reachable before considering a restart.", "Check the service health endpoint."],
        "service-unhealthy": [f"Read the health-check output and recent logs for {subject}.", "Verify storage, DNS, and network dependencies.", "Check the service health endpoint independently."],
        "missing-dependency": [f"Resolve the missing graph reference reported by {subject}.", "Verify the dependency exists and is reachable.", "Re-run the doctor to confirm the graph is complete."],
        "recovery-unproven": [f"Verify {subject} is mounted and readable from its consumers.", "Locate the latest backup and required recovery keys.", "Do not treat backup freshness as restore proof."],
        "evidence-gap": [f"Restore read-only access to the {subject} evidence source.", "Re-run discovery before taking corrective action."],
        "recent-change": [f"Confirm the recorded change for {subject} was intentional.", "Compare health before and after the change.", "Verify dependents without changing them."],
    }
    return plans.get(code, [f"Inspect {subject} with a read-only check.", "Verify upstream dependencies and downstream impact."])


def event_is_recent(event_at: str, observed_at: str, hours: int = 24) -> bool:
    try:
        event_time = datetime.fromisoformat(event_at.replace("Z", "+00:00"))
        observed_time = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        age = observed_time - event_time
        return 0 <= age.total_seconds() <= hours * 3600
    except (ValueError, TypeError):
        return event_at == observed_at


def investigate(report: dict[str, Any], inventory: dict[str, Any], requested_target: str) -> dict[str, Any]:
    known = sorted({item_id(item) for group in ("nodes", "services", "storage") for item in inventory.get(group, [])})
    target = next((candidate for candidate in known if candidate.casefold() == requested_target.casefold()), None)
    if not target:
        return {
            "target": requested_target, "status": "target-not-found", "dependencies": [], "impacted": [],
            "hypotheses": [], "suggestions": difflib.get_close_matches(requested_target, known, n=5, cutoff=0.3),
            "conclusion": "The target is not present in discovered or declared inventory.",
        }

    dependencies = reachable(target, report["relationships"])
    relevant = {target, *dependencies}
    candidates: list[dict[str, Any]] = []
    finding_scores = {
        "service-not-running": 96, "service-unhealthy": 92, "missing-dependency": 85,
        "service-unrecoverable": 35, "service-recovery-unproven": 25,
        "evidence-gap": 48, "recovery-unproven": 38, "broad-listen": 25,
        "public-service": 25, "shared-dependency": 20,
    }
    for finding in report["findings"]:
        if finding["subject"] not in relevant and finding["code"] != "evidence-gap":
            continue
        score = finding_scores.get(finding["code"], 30)
        if finding["subject"] in dependencies:
            score -= 5
        if finding["code"] == "evidence-gap" and finding["subject"] not in relevant:
            score -= 15
        candidates.append({
            "score": max(score, 1), "code": finding["code"], "subject": finding["subject"],
            "summary": finding["summary"],
            "supporting_evidence": [f"{finding['severity']} finding: {finding['code']} on {finding['subject']}"],
        })

    timeline = report.get("timeline", {})
    for event in timeline.get("events", []):
        if not event_is_recent(event["at"], report["observed_at"]) or event["subject"] not in relevant:
            continue
        score = 88 if event["change"] in {"state", "health", "removed"} else 72 if event["change"] in {"image", "runs_on", "exposure"} else 55
        candidates.append({
            "score": score, "code": "recent-change", "subject": event["subject"],
            "summary": f"Recent {event['change']} change: {event['before']} → {event['after']}.",
            "supporting_evidence": [f"timeline event at {event['at']} for {event['subject']}"],
        })

    candidates.sort(key=lambda item: (-item["score"], item["code"], item["subject"]))
    hypotheses: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        key = (candidate["code"], candidate["subject"])
        if key in seen:
            continue
        seen.add(key)
        score = candidate.pop("score")
        confidence = "likely" if score >= 80 else "possible" if score >= 50 else "weak-signal"
        root = candidate["subject"]
        hypotheses.append({
            "rank": len(hypotheses) + 1, "confidence": confidence, "score": score, **candidate,
            "impacted": [item for item in reachable(root, report["relationships"], reverse=True) if item != root],
            "recommended_action": "Gather the verification evidence below before changing infrastructure.",
            "verification": verification_for(candidate["code"], root),
        })
        if len(hypotheses) == 5:
            break

    if not hypotheses:
        hypotheses.append({
            "rank": 1, "confidence": "insufficient-evidence", "score": 0, "code": "no-observed-symptom",
            "subject": target, "summary": "No current symptom or relevant recent change explains the incident.",
            "supporting_evidence": [], "impacted": reachable(target, report["relationships"], reverse=True),
            "recommended_action": "Collect live health, logs, DNS, network, and storage evidence before changing anything.",
            "verification": verification_for("unknown", target),
        })
    top = hypotheses[0]
    if top["score"] >= 50:
        conclusion = f"Top hypothesis ({top['confidence']}): {top['subject']} — {top['summary']}"
    elif top["score"]:
        conclusion = f"No likely cause is established. Strongest weak signal: {top['subject']} — {top['summary']}"
    else:
        conclusion = top["summary"]
    return {
        "target": target, "status": "investigated", "dependencies": dependencies,
        "impacted": reachable(target, report["relationships"], reverse=True),
        "hypotheses": hypotheses, "suggestions": [], "conclusion": conclusion,
    }


def redact(text: str) -> str:
    text = PRIVATE_VALUE.sub("[redacted-private-address]", text)
    return HOME_PATH.sub(r"\1[redacted-user]", text)


def create_diagnostic_bundle(report: dict[str, Any], output: Path) -> list[str]:
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"bundle directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    markdown = redact(render_markdown(report, shared=True))
    machine = redact(json.dumps(report, indent=2, sort_keys=True) + "\n")
    files = ["report.md", "report.json", "manifest.json", "README.md"]
    (output / "report.md").write_text(markdown, encoding="utf-8")
    (output / "report.json").write_text(machine, encoding="utf-8")
    manifest = {
        "format_version": 1,
        "created_at": report["observed_at"],
        "generator": "agentic-homelab doctor",
        "read_only": True,
        "files": files,
        "excluded": ["raw inventory", "environment values", "credentials", "response bodies",
                     "raw logs", "command output", "addresses", "home-directory usernames"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "README.md").write_text(
        "# agentic-homelab diagnostic bundle\n\n"
        "Start with `report.md`; use `report.json` for machine analysis. This bundle contains the same "
        "read-only diagnosis, graph, timeline, recovery, update, and incident evidence.\n\n"
        "Private addresses and home-directory usernames were redacted. Raw inventory, environment values, "
        "credentials, endpoint URLs/bodies, logs, and command output were excluded. Redaction reduces accidental "
        "disclosure but cannot understand arbitrary names: review every file before sharing.\n",
        encoding="utf-8",
    )
    return files


def render_markdown(report: dict[str, Any], shared: bool = False) -> str:
    summary = report["summary"]
    lines = [
        f"# {report['homelab']}: explained",
        "",
        (f"Found **{summary['nodes']} nodes**, **{summary['services']} services**, "
         f"**{summary['storage']} storage systems**, and **{summary['relationships']} relationships**."),
        f"Found **{summary['risks']} risks** and **{summary['unknowns']} unknowns**.",
    ]
    investigation = report.get("investigation")
    if investigation:
        lines.extend(["", f"## Why is {investigation['target']} broken?", "", investigation["conclusion"], ""])
        if investigation["status"] == "target-not-found":
            if investigation["suggestions"]:
                lines.append("Did you mean: " + ", ".join(f"`{item}`" for item in investigation["suggestions"]) + "?")
            lines.append("No corrective action is recommended until the target is identified.")
        else:
            lines.append("Ranked hypotheses:")
            lines.append("")
            for hypothesis in investigation["hypotheses"]:
                lines.extend([
                    f"### {hypothesis['rank']}. [{hypothesis['confidence'].upper()}] {hypothesis['subject']}", "",
                    hypothesis["summary"], "",
                    "Supporting evidence: " + ("; ".join(hypothesis["supporting_evidence"]) or "none yet"), "",
                    ("Potential impact: " + ", ".join(f"`{item}`" for item in hypothesis["impacted"]))
                    if hypothesis["impacted"] else "Potential impact: no downstream dependents are known.", "",
                    hypothesis["recommended_action"], "",
                    "Verification:", "",
                    *[f"- {step}" for step in hypothesis["verification"]], "",
                ])
            if investigation["dependencies"]:
                lines.append("Dependencies inspected: " + ", ".join(f"`{item}`" for item in investigation["dependencies"]))
            lines.extend(["", "No changes have been made."])
    lines.extend(["", "## What is at risk", ""])
    if report["findings"]:
        for finding in report["findings"]:
            lines.extend([
                f"### [{finding['severity'].upper()}] {finding['subject']}: {finding['code']}",
                "",
                finding["summary"],
                "",
                f"Recommended next step: {finding['recommendation']}",
                "",
            ])
    else:
        lines.extend(["No obvious risks were found in the supplied inventory.", ""])

    readiness = report.get("recovery_readiness")
    if readiness:
        counts = readiness["summary"]
        lines.extend([
            "## Can I recover it?", "",
            (f"**{counts['proven']} proven**, **{counts['partial']} partial**, "
             f"**{counts['unproven']} unproven**, **{counts['unrecoverable']} unrecoverable**."), "",
            readiness["principle"], "",
        ])
        for service in readiness["services"]:
            lines.extend([f"### {service['service']}: {service['status']} ({service['score']}%)", ""])
            for check in service["checks"]:
                lines.append(f"- [{check['state'].upper()}] {check['name']}: {check['evidence']}")
            if service["next_actions"]:
                lines.extend(["", "Next evidence to gather:", ""])
                lines.extend(f"- {action}" for action in service["next_actions"])
            lines.append("")

    updates = report.get("update_intelligence")
    if updates:
        lines.extend(["## What can I safely update?", "", updates["principle"], ""])
        if not updates["plans"]:
            lines.extend(["No matching service was found.", ""])
        for plan in updates["plans"]:
            lines.extend([f"### {plan['service']}: {plan['decision']}", "",
                f"Version: `{plan['current_version'] or 'unknown'}` → `{plan['target_version'] or 'unknown'}`", "",
                plan["reason"], ""])
            for gate in plan["gates"]:
                lines.append(f"- [{gate['state'].upper()}] {gate['name']}: {gate['evidence']}")
            if plan["blast_radius"]:
                lines.extend(["", "Potential blast radius: " + ", ".join(f"`{item}`" for item in plan["blast_radius"]), ""])
            if plan["plan"]:
                lines.extend(["", "Human-controlled plan:", ""])
                lines.extend(f"{index}. {step}" for index, step in enumerate(plan["plan"], 1))
                lines.append("")

    lines.extend(["## Homelab graph", ""])
    if report["relationships"]:
        lines.extend(f"- `{edge['source']}` —{edge['relation']}→ `{edge['target']}`" for edge in report["relationships"])
    else:
        lines.append("No relationships could be inferred yet.")
    lines.extend(["", "## What changed", ""])
    timeline = report.get("timeline")
    if not timeline:
        lines.append("Change history is disabled or unavailable.")
    elif timeline["status"] == "baseline":
        lines.append("Baseline recorded. Run the doctor again to compare observations.")
    elif not timeline["events"]:
        lines.append(f"No tracked changes since {timeline['previous_observed_at']}.")
    else:
        for event in timeline["events"]:
            if event["change"] == "added":
                description = "added"
            elif event["change"] == "removed":
                description = "removed"
            else:
                description = f"{event['change']}: {event['before']} → {event['after']}"
            lines.append(f"- {event['at']} [{event['severity'].upper()}] `{event['subject']}` ({event['category']}): {description}")
    lines.extend(["", "## What is still unknown", ""])
    lines.extend(f"- {unknown}" for unknown in report["unknowns"])
    if not report["unknowns"]:
        lines.append("No inventory gaps detected.")
    lines.extend(["", "## Evidence", ""])
    for evidence in report["evidence"]:
        lines.append(f"- **{evidence['source']}** [{evidence['status']}]: {evidence['detail']}")
    lines.extend([
        "",
        "---",
        "No changes have been made. Findings distinguish live observations from declared or unavailable evidence.",
    ])
    if shared:
        lines.append("Private addresses were automatically redacted. Review before sharing.")
        lines.append("Generated with agentic-homelab.")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, help="Optional YAML or JSON inventory to enrich local discovery")
    parser.add_argument("--no-discover", action="store_true", help="Use only declared inventory")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--share", type=Path, help="Write a redacted Markdown report safe to review and share")
    parser.add_argument("--bundle", type=Path, help="Write a redacted diagnostic bundle to an empty directory")
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY, help="Local observation history path")
    parser.add_argument("--no-history", action="store_true", help="Do not read or write observation history")
    parser.add_argument("--investigate", metavar="COMPONENT", help="Rank read-only root-cause hypotheses for a service or component")
    parser.add_argument("--plan-updates", nargs="?", const="", metavar="SERVICE",
                        help="Assess all declared update candidates, or one service")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    declared = load_inventory(args.inventory) if args.inventory else {}
    discovered, evidence = ({}, []) if args.no_discover else discover_local()
    if args.inventory:
        evidence.insert(0, {"source": "inventory", "status": "declared", "detail": str(args.inventory)})
    inventory = merge_inventory(declared, discovered)
    if not args.no_discover:
        endpoint_inventory, endpoint_evidence = endpoint_discovery(inventory)
        inventory = merge_observations(inventory, endpoint_inventory)
        evidence.append(endpoint_evidence)
    observed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report = inspect_inventory(inventory, evidence)
    report["observed_at"] = observed_at
    if not args.no_history:
        history = load_history(args.history)
        current = make_snapshot(inventory, observed_at)
        attach_timeline(report, build_timeline(history, current))
        save_history(args.history, history, current)
    attach_external_changes(report, inventory.get("changes", []))
    attach_recovery_readiness(report, inventory)
    if args.plan_updates is not None:
        attach_update_intelligence(report, inventory, args.plan_updates or None)
    if args.investigate:
        report["investigation"] = investigate(report, inventory, args.investigate)
    output = json.dumps(report, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_markdown(report)
    print(output, end="")
    if args.share:
        args.share.parent.mkdir(parents=True, exist_ok=True)
        args.share.write_text(redact(render_markdown(report, shared=True)), encoding="utf-8")
        print(f"Shareable report written to {args.share}", file=sys.stderr)
    if args.bundle:
        try:
            create_diagnostic_bundle(report, args.bundle)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"Diagnostic bundle written to {args.bundle}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
