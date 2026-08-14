#!/usr/bin/env python3
"""Produce a release-readiness audit for agentic-homelab."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


def run_command(args: list[str], timeout: int = 60) -> tuple[bool, str]:
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
    output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part)
    return proc.returncode == 0, output


def file_contains(path: str, required: list[str]) -> tuple[bool, str]:
    target = ROOT / path
    if not target.exists():
        return False, f"missing {path}"
    text = target.read_text(encoding="utf-8").lower()
    missing = [item for item in required if item.lower() not in text]
    if missing:
        return False, f"{path} missing: {', '.join(missing)}"
    return True, f"{path} contains required release signals"


def path_exists(path: str) -> tuple[bool, str]:
    target = ROOT / path
    return target.exists(), f"{path} {'exists' if target.exists() else 'is missing'}"


def audited_item(name: str, status: str, evidence: str) -> dict[str, str]:
    return {"name": name, "status": status, "evidence": evidence}


def build_audit(run_validate: bool) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    catalog = yaml.safe_load((ROOT / "catalog" / "index.yaml").read_text(encoding="utf-8"))
    repository = catalog.get("repository", {})

    if run_validate:
        ok, output = run_command([sys.executable, "scripts/validate_repo.py"], timeout=60)
        items.append(audited_item("Repository validator passes", "pass" if ok else "fail", output))
        ok, output = run_command([sys.executable, "scripts/smoke_mcp.py"], timeout=60)
        items.append(audited_item("MCP smoke tests pass", "pass" if ok else "fail", output))
        with tempfile.TemporaryDirectory(prefix="agentic-homelab-release-") as output_dir:
            ok, output = run_command([sys.executable, "-m", "build", "--outdir", output_dir], timeout=120)
            items.append(audited_item("Python sdist and wheel build", "pass" if ok else "fail", output))
            if ok:
                artifacts = sorted(str(path) for path in Path(output_dir).iterdir())
                ok, output = run_command([sys.executable, "-m", "twine", "check", *artifacts], timeout=60)
                items.append(audited_item("Python package metadata passes twine", "pass" if ok else "fail", output))
    else:
        items.append(audited_item("Repository validator passes", "manual", "Run `make validate` before release."))

    checks = [
        ("README describes current status honestly", "README.md", ["Current Status", "smoke-tested against", "implemented-capabilities"]),
        ("README has release-grade OSS structure", "README.md", ["What This Is", "What This Is Not", "Quick Start", "Supported Domains", "Supported Clients", "License"]),
        ("README includes skills install shorthand", "README.md", [repository.get("skills_install", "npx skills add")]),
        ("Security policy is present", "SECURITY.md", ["Security", "report"]),
        ("Code of conduct is present", "CODE_OF_CONDUCT.md", ["Expected Behavior", "Reporting"]),
        ("Changelog is present", "CHANGELOG.md", ["0.1.0", "Unreleased"]),
        ("Documentation index is present", "docs/index.md", ["Start", "Safety", "Client Quickstarts"]),
        ("Release readiness doc is present", "docs/release-readiness.md", ["Required", "Strongly Recommended"]),
        ("Implemented capabilities boundary is documented", "docs/implemented-capabilities.md", ["Implemented Reference MCP Servers", "Intentionally Not Implemented"]),
        ("Incident demo is reproducible", "docs/assets/demo.tape", ["homelab investigate jellyfin", "docs/assets/demo-incident"]),
        ("Client compatibility docs cover named clients", "docs/client-compatibility.md", ["OpenClaw", "Hermes", "Claude", "Codex", "Cursor", "Grok"]),
        ("Action risk matrix docs are present", "docs/action-risk-matrix.md", ["destructive", "required evidence"]),
        ("Threat model is present", "docs/threat-model.md", ["Assets", "Primary Risks"]),
    ]
    for name, path, required in checks:
        ok, evidence = file_contains(path, required)
        items.append(audited_item(name, "pass" if ok else "fail", evidence))

    required_paths = [
        ".github/workflows/validate.yml",
        ".github/pull_request_template.md",
        ".github/ISSUE_TEMPLATE/integration_request.md",
        "docs/assets/demo.gif",
        "docs/assets/demo-incident.inventory.yaml",
        "pyproject.toml",
        "scripts/bootstrap_homelab_repo.py",
        "scripts/choose_workflow.py",
        "scripts/guardrail_check.py",
        "guardrails/action-risk-matrix.yaml",
        "guardrails/policies/default-policy.yaml",
        "templates/agent-instructions/AGENTS.md",
    ]
    for path in required_paths:
        ok, evidence = path_exists(path)
        items.append(audited_item(f"Required release asset: {path}", "pass" if ok else "fail", evidence))

    for skill in ["homelab-setup", "infrastructure-maintenance", "agent-self-management", "safety-harness"]:
        for suffix in ["SKILL.md", "LICENSE.txt", "agents/openai.yaml"]:
            path = f"skills/{skill}/{suffix}"
            ok, evidence = path_exists(path)
            items.append(audited_item(f"Skill package asset: {path}", "pass" if ok else "fail", evidence))

    manual_items = [
        ("Fresh clone validation", "Have another machine/user run `make validate` from a clean clone."),
        ("Claude Desktop config load", "Generate MCP config and verify at least one client accepts the paths after local adjustment."),
        ("Real Proxmox token check", "Test docs/proxmox-readonly-token.md against a scoped non-root Proxmox token."),
        ("Real Docker host check", "Run Docker read-only tools on a real Docker host."),
        ("Diagnostics on macOS and Linux", "Run diagnostics bundle workflow on both platforms before broad release claims."),
    ]
    for name, evidence in manual_items:
        items.append(audited_item(name, "manual", evidence))

    return items


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--run-validate", action="store_true", help="Run validator and MCP smoke tests as part of the audit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    items = build_audit(args.run_validate)
    failed = [item for item in items if item["status"] == "fail"]

    if args.format == "json":
        print(json.dumps({"items": items, "failed": len(failed)}, indent=2))
    else:
        print("Release readiness audit")
        for item in items:
            print(f"- [{item['status']}] {item['name']}")
            print(f"  {item['evidence']}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
