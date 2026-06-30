#!/usr/bin/env python3
"""Classify a homelab action against MCP manifests and the action risk matrix."""

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
APPROVAL_RISKS = {"write", "destructive", "credential-access"}


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def find_tool(action: str, server: str | None = None) -> dict[str, Any] | None:
    for path in sorted((ROOT / "packages" / "mcp-servers").glob("*/mcp.yaml")):
        manifest = load_yaml(path)
        if server and manifest["id"] != server:
            continue
        for tool in manifest.get("tools", []):
            if tool.get("name") == action:
                return {"server": manifest["id"], "manifest": str(path.relative_to(ROOT)), **tool}
    return None


def find_matrix_category(action: str) -> dict[str, Any] | None:
    path = ROOT / "guardrails" / "action-risk-matrix.yaml"
    matrix = load_yaml(path)
    normalized = action.strip().lower().replace("_", "-")
    for category in matrix.get("categories", []):
        if category.get("id") == normalized:
            return {"matrix": str(path.relative_to(ROOT)), **category}
    return None


def classify(action: str, server: str | None = None) -> dict[str, Any]:
    tool = find_tool(action, server)
    if not tool:
        category = find_matrix_category(action)
        if category:
            decision = category.get("decision", "unknown_requires_review")
            if decision == "allow_readonly":
                next_step = "Proceed only if the concrete command/tool is read-only and output is bounded/redacted."
            elif decision == "destructive_approval_required":
                next_step = "Stop for separate destructive-action approval that repeats the exact target and verifier."
            elif decision == "unknown_requires_review":
                next_step = "Do not execute. Classify the concrete action or use read-only discovery first."
            else:
                next_step = "Stop for approval with target, exact command/tool, expected effect, rollback, and verifier."
            return {
                "action": action,
                "server": server,
                "decision": decision,
                "risk": category.get("id"),
                "requires_approval": bool(category.get("requires_approval")),
                "examples": category.get("examples", []),
                "required_evidence": category.get("required_evidence", []),
                "matrix": category["matrix"],
                "next_step": next_step,
            }
        return {
            "action": action,
            "server": server,
            "decision": "unknown_requires_review",
            "risk": "unknown",
            "reason": "Action is not declared in known MCP manifests. Treat as write-risk until classified.",
            "next_step": "Use read-only discovery or add a manifest entry before execution.",
        }

    risk = tool.get("risk", "unknown")
    requires_approval = bool(tool.get("requires_approval")) or risk in APPROVAL_RISKS
    if risk in {"read", "plan"} and not requires_approval:
        decision = "allow_readonly"
        next_step = "Run only within the declared read/plan behavior and keep output bounded/redacted."
    else:
        decision = "approval_required"
        next_step = "Before execution, state target, exact command/tool, expected effect, rollback, and verifier."

    return {
        "action": action,
        "server": tool["server"],
        "decision": decision,
        "risk": risk,
        "requires_approval": requires_approval,
        "description": tool.get("description", ""),
        "manifest": tool["manifest"],
        "next_step": next_step,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", help="MCP tool or matrix category, for example list_nodes, delete_guest, network-exposure")
    parser.add_argument("--server", help="Optional MCP server id to disambiguate")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = classify(args.action, args.server)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"action: {result['action']}")
        print(f"server: {result.get('server')}")
        print(f"decision: {result['decision']}")
        print(f"risk: {result['risk']}")
        if result.get("required_evidence"):
            print("required_evidence:")
            for evidence in result["required_evidence"]:
                print(f"- {evidence}")
        print(f"next_step: {result['next_step']}")
    return 0 if result["decision"] == "allow_readonly" else 2


if __name__ == "__main__":
    raise SystemExit(main())
