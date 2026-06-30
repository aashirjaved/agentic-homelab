#!/usr/bin/env python3
"""Recommend safe starter workflows from a homelab inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing PyYAML. Install with: python3 -m pip install pyyaml") from exc


ROOT = Path(__file__).resolve().parents[1]


def load_inventory(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"Inventory must be an object: {path}")
    return data


def values_for(items: list[dict[str, Any]], key: str) -> set[str]:
    return {str(item.get(key, "")).lower() for item in items if item.get(key)}


def add_recommendation(recommendations: list[dict[str, Any]], workflow: str, reason: str, priority: int) -> None:
    path = ROOT / "examples" / workflow / "workflow.yaml"
    recommendations.append(
        {
            "workflow": workflow,
            "path": str(path.relative_to(ROOT)),
            "priority": priority,
            "reason": reason,
            "safety_note": "Start read-only. Treat workflow plans as proposals, not approval.",
        }
    )


def recommend(data: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = data.get("nodes", []) or []
    services = data.get("services", []) or []
    storage = data.get("storage", []) or []
    agents = data.get("agents", []) or []
    networks = data.get("networks", {}) or {}

    node_roles = values_for(nodes, "role")
    service_kinds = values_for(services, "kind")
    storage_kinds = values_for(storage, "kind")
    agent_kinds = values_for(agents, "kind")
    backup_statuses = values_for(storage, "backup_status")
    service_exposures = values_for(services, "exposure")

    recommendations: list[dict[str, Any]] = []

    if "proxmox" in node_roles or any("proxmox" in kind for kind in storage_kinds):
        add_recommendation(recommendations, "proxmox-vm-maintenance", "Inventory includes Proxmox compute or storage.", 10)

    if "docker-host" in node_roles or any(kind in service_kinds for kind in {"media", "media-automation", "ingress"}):
        add_recommendation(recommendations, "docker-stack-maintenance", "Inventory includes Docker/media-style services.", 20)

    has_storage_or_backup = (
        any("nas" in role for role in node_roles)
        or any("nas" in kind or "backup" in kind for kind in storage_kinds)
        or bool(backup_statuses)
    )

    if has_storage_or_backup:
        add_recommendation(recommendations, "media-server-nas", "Inventory includes NAS, shares, media storage, or backup targets.", 30)

    if agents or any("agent" in kind for kind in service_kinds | agent_kinds) or "agent-runtime" in node_roles:
        add_recommendation(recommendations, "local-agent-runtime", "Inventory includes local agents or an agent runtime host.", 40)

    if len(nodes) > 1 or networks or service_exposures:
        add_recommendation(recommendations, "multi-node-monitoring", "Inventory has multiple nodes, network context, or service exposure metadata.", 50)

    if backup_statuses or any(status in backup_statuses for status in {"unknown", "needs-restore-test", "needs-offsite-copy"}):
        add_recommendation(recommendations, "backup-restore-drill", "Inventory includes backup status; verify restore evidence before risky maintenance.", 55)
        add_recommendation(recommendations, "diagnostics-bundle", "Inventory includes storage or backup status worth capturing in redacted diagnostics.", 60)

    if not recommendations:
        add_recommendation(recommendations, "diagnostics-bundle", "No specific domain detected; begin with redacted diagnostics and inventory cleanup.", 100)

    return sorted(recommendations, key=lambda item: item["priority"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path, help="YAML or JSON inventory file")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = load_inventory(args.inventory)
    recommendations = recommend(data)

    if args.format == "json":
        print(json.dumps({"recommendations": recommendations}, indent=2))
        return 0

    print(f"Recommended workflows for {args.inventory}:")
    for item in recommendations:
        print(f"- {item['workflow']} ({item['path']})")
        print(f"  reason: {item['reason']}")
        print(f"  safety: {item['safety_note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
