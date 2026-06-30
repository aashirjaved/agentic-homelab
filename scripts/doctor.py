#!/usr/bin/env python3
"""Preflight checks for using agentic-homelab safely."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OPTIONAL_CLIS = ["docker", "tailscale", "smartctl", "virsh", "zpool"]
REQUIRED_PATHS = [
    "README.md",
    "guardrails/policies/default-policy.yaml",
    "packages/mcp-servers/proxmox/server.py",
    "packages/mcp-servers/docker/server.py",
    "packages/mcp-servers/networking/server.py",
    "packages/mcp-servers/storage-nas/server.py",
    "packages/mcp-servers/monitoring/server.py",
    "packages/mcp-servers/vm-management/server.py",
]


def check(status: str, name: str, detail: str) -> dict[str, str]:
    return {"status": status, "name": name, "detail": detail}


def path_checks() -> list[dict[str, str]]:
    results = []
    for rel in REQUIRED_PATHS:
        path = ROOT / rel
        results.append(check("pass" if path.exists() else "fail", f"path:{rel}", "present" if path.exists() else "missing"))
    return results


def cli_checks() -> list[dict[str, str]]:
    results = [check("pass", "python", sys.version.split()[0])]
    for cli in OPTIONAL_CLIS:
        found = shutil.which(cli)
        results.append(check("pass" if found else "warn", f"optional-cli:{cli}", found or "not found; related tools degrade gracefully"))
    return results


def inventory_check(inventory: Path | None) -> list[dict[str, str]]:
    if not inventory:
        return [check("warn", "inventory", "not provided; use templates/inventory/")]
    if inventory.exists():
        return [check("pass", "inventory", str(inventory))]
    return [check("fail", "inventory", f"missing: {inventory}")]


def proxmox_env_check() -> list[dict[str, str]]:
    names = ["PROXMOX_API_URL", "PROXMOX_API_TOKEN_ID", "PROXMOX_API_TOKEN_SECRET"]
    present = [name for name in names if os.environ.get(name)]
    if len(present) == len(names):
        return [check("pass", "proxmox-api-env", "read-only API env appears configured")]
    if present:
        return [check("warn", "proxmox-api-env", f"partial config: {', '.join(present)}")]
    return [check("warn", "proxmox-api-env", "not configured; Proxmox server can still use JSON inventory fallback")]


def run_quick_command(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(args, cwd=ROOT, check=False, capture_output=True, text=True, timeout=20)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def validation_check() -> list[dict[str, str]]:
    code, output = run_quick_command([sys.executable, "scripts/smoke_mcp.py"])
    if code == 0:
        return [check("pass", "mcp-smoke", "reference MCP servers respond")]
    return [check("fail", "mcp-smoke", output[-500:])]


def run_doctor(inventory: Path | None) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    results.extend(path_checks())
    results.extend(cli_checks())
    results.extend(inventory_check(inventory))
    results.extend(proxmox_env_check())
    results.extend(validation_check())
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, help="Optional inventory path to check")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = run_doctor(args.inventory)
    if args.format == "json":
        print(json.dumps({"checks": results}, indent=2, sort_keys=True))
    else:
        for item in results:
            print(f"[{item['status']}] {item['name']}: {item['detail']}")
    return 1 if any(item["status"] == "fail" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

