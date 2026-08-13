#!/usr/bin/env python3
"""Classify a homelab action against MCP manifests and the action risk matrix."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing PyYAML. Run `make validate` once, then `source .venv/bin/activate` "
        "(system pip installs are often blocked by PEP 668)."
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
APPROVAL_RISKS = {"write", "destructive", "credential-access"}

# Known-destructive command shapes force-classify as destructive whatever label
# the agent supplies. Best-effort pattern list, not a shell parser: it narrows
# the self-labeling trust gap for obvious cases and will not catch every
# obfuscation. Matched against a whitespace-normalized lowercase string.
DENY_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\brm\s+-\S*r\S*f",       # rm -rf, rm -fr, rm -r -f (after normalize)
        r"\brm\s+-\S*f\S*r",
        r"\brm\s+-r\b.*\s-f\b",
        r"\bmkfs",
        r"\bdd\s+\S*.*\bof=/dev/",
        r"\bwipefs",
        r"\bzfs\s+destroy",
        r"\bqm\s+destroy",
        r"\bpct\s+destroy",
        r"\bdocker\s+system\s+prune",
        r"\btruncate\s+(-s|--size)\s+0\b",
        r"\bshred\b",
    )
)


def matches_deny_pattern(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.lower())
    return any(pattern.search(normalized) for pattern in DENY_PATTERNS)


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


def load_policy() -> dict[str, Any]:
    path = ROOT / "guardrails" / "policies" / "default-policy.yaml"
    if not path.exists():
        return {}
    policy = load_yaml(path) or {}
    policy["_path"] = str(path.relative_to(ROOT))
    return policy


def apply_policy(result: dict[str, Any]) -> dict[str, Any]:
    """Escalation-only overlay: the policy can tighten a decision, never relax one.

    With the shipped defaults the classifier is already at least as strict as
    the policy, so this layer is defense in depth: it catches future classifier
    relaxation, custom manifests that mislabel risk, and policy typos (an
    unrecognized mode fails closed to read-only).
    """
    policy = load_policy()
    if not policy:
        return result
    defaults = policy.get("defaults", {})
    mode = defaults.get("mode", "read-only")
    if mode != "read-only":
        # Unknown modes must not silently disable escalation.
        result["policy_warning"] = (
            f"Unrecognized policy mode {mode!r}; treating as read-only (fail closed)."
        )
        mode = "read-only"
    require_approval = set(defaults.get("require_approval_for", []))
    risk = result.get("risk")
    if result.get("decision") == "allow_readonly" and (
        risk in require_approval or risk not in {"read", "plan"}
    ):
        result["decision"] = "approval_required"
        result["requires_approval"] = True
        result["next_step"] = (
            "Policy requires approval for this risk. State target, exact command/tool, "
            "expected effect, rollback, and verifier."
        )
    result["policy"] = {"name": policy.get("name"), "mode": mode, "path": policy["_path"]}
    return result


def classify(action: str, server: str | None = None) -> dict[str, Any]:
    if matches_deny_pattern(action):
        category = find_matrix_category("destructive") or {}
        return {
            "action": action,
            "server": server,
            "decision": "destructive_approval_required",
            "risk": "destructive",
            "requires_approval": True,
            "reason": "Action matches a known-destructive pattern; label is ignored.",
            "required_evidence": category.get("required_evidence", []),
            "next_step": "Stop for separate destructive-action approval that repeats the exact target and verifier.",
        }
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
    required_evidence: list[str] = []
    if risk in {"read", "plan"} and not requires_approval:
        decision = "allow_readonly"
        next_step = "Run only within the declared read/plan behavior and keep output bounded/redacted."
    elif risk == "destructive":
        decision = "destructive_approval_required"
        next_step = "Stop for separate destructive-action approval that repeats the exact target and verifier."
        category = find_matrix_category("destructive") or {}
        required_evidence = category.get("required_evidence", [])
    else:
        decision = "approval_required"
        next_step = "Before execution, state target, exact command/tool, expected effect, rollback, and verifier."

    result = {
        "action": action,
        "server": tool["server"],
        "decision": decision,
        "risk": risk,
        "requires_approval": requires_approval,
        "description": tool.get("description", ""),
        "manifest": tool["manifest"],
        "next_step": next_step,
    }
    if required_evidence:
        result["required_evidence"] = required_evidence
    return result


def hook_main() -> int:
    """PreToolUse hook mode: read the hook JSON from stdin, emit a permission decision.

    Always exits 0 with a JSON decision on stdout; any internal error emits a
    deny (fail closed). Tool names arrive as mcp__<server>__<tool>; string
    values inside tool_input are also screened against the deny patterns so
    command-shaped arguments cannot sneak past a harmless tool name.
    """
    def emit(decision: str, reason: str) -> int:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            }
        }))
        return 0

    try:
        payload = json.load(sys.stdin)
        tool_name = str(payload.get("tool_name", ""))
        if not tool_name:
            return emit("deny", "Hook payload has no tool_name; failing closed.")
        parts = tool_name.split("__")
        action = parts[-1]
        server = None
        if len(parts) == 3 and parts[0] == "mcp":
            server = parts[1].removeprefix("agentic-homelab-")
        arg_text = " ".join(
            str(v) for v in (payload.get("tool_input") or {}).values() if isinstance(v, (str, int, float))
        )
        if arg_text and matches_deny_pattern(arg_text):
            return emit("deny", f"Tool arguments match a known-destructive pattern: {arg_text[:200]}")
        result = apply_policy(classify(action, server))
        decision = result["decision"]
        if decision == "allow_readonly":
            return emit("allow", f"{action}: read-only per {result.get('manifest', 'risk matrix')}.")
        if decision == "approval_required":
            return emit("ask", f"{action}: {result['next_step']}")
        return emit("deny", f"{action}: {decision}. {result['next_step']}")
    except Exception as exc:  # fail closed, never fail open
        return emit("deny", f"guardrail hook error ({exc}); failing closed.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", help="MCP tool or matrix category, for example list_nodes, delete_guest, network-exposure")
    parser.add_argument("--server", help="Optional MCP server id to disambiguate")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--hook", action="store_true", help="PreToolUse hook mode: read hook JSON from stdin, print a permission decision, always exit 0")
    args = parser.parse_args()
    if not args.hook and not args.action:
        parser.error("action is required unless --hook is used")
    return args


def main() -> int:
    args = parse_args()
    if args.hook:
        return hook_main()
    result = apply_policy(classify(args.action, args.server))
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
        if result.get("policy"):
            print(f"policy: {result['policy']['name']} (mode: {result['policy']['mode']})")
    return 0 if result["decision"] == "allow_readonly" else 2


if __name__ == "__main__":
    raise SystemExit(main())
