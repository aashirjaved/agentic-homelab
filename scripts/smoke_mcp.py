#!/usr/bin/env python3
"""Smoke-test reference MCP servers without requiring live infrastructure."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import importlib.util
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def run_server(script: Path, messages: list[dict[str, Any]], env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    payload = "\n".join(json.dumps(message) for message in messages) + "\n"
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
        env={**os.environ, **(env or {})},
    )
    if proc.returncode != 0:
        raise AssertionError(f"{script} exited {proc.returncode}: {proc.stderr}")
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def assert_tool_list(script: Path, expected_tools: set[str], env: dict[str, str] | None = None) -> None:
    responses = run_server(
        script,
        [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ],
        env=env,
    )
    tools = {tool["name"] for tool in responses[1]["result"]["tools"]}
    missing = expected_tools - tools
    if missing:
        raise AssertionError(f"{script} missing tools: {sorted(missing)}")


def assert_proxmox_inventory() -> None:
    responses = run_server(
        ROOT / "packages" / "mcp-servers" / "proxmox" / "server.py",
        [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "list_nodes", "arguments": {}},
            }
        ],
        env={"AGENTIC_HOMELAB_INVENTORY": str(ROOT / "templates" / "inventory" / "homelab.inventory.example.json")},
    )
    text = responses[0]["result"]["content"][0]["text"]
    if "pve-01" not in text:
        raise AssertionError("Proxmox inventory smoke test did not include pve-01")


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_proxmox_api_formatting() -> None:
    module = load_module(ROOT / "packages" / "mcp-servers" / "proxmox" / "server.py", "proxmox_server")

    fixtures: dict[str, Any] = {
        "/nodes": [{"node": "pve-01", "status": "online", "cpu": 0.1, "mem": 1024, "uptime": 99}],
        "/cluster/resources?type=vm": [
            {"node": "pve-01", "type": "qemu", "vmid": 100, "name": "media", "status": "running", "cpu": 0.2, "mem": 2048}
        ],
        "/nodes/pve-01/qemu/100/config": {"name": "media", "memory": 2048, "agent": 1, "secret_note": "redact-me"},
        "/storage": [{"storage": "local-lvm", "type": "lvmthin", "enabled": 1, "active": 1, "content": "images,rootdir"}],
        "/cluster/tasks?limit=20": [
            {"node": "pve-01", "upid": "UPID:pve-01:1", "type": "qmstart", "status": "OK", "user": "root@pam"}
        ],
    }

    def fake_api_data(path: str) -> Any:
        if path not in fixtures:
            raise AssertionError(f"Unexpected Proxmox API path: {path}")
        return fixtures[path]

    module.api_data = fake_api_data
    module.api_configured = lambda: True

    checks = [
        ("list_nodes", {}, "pve-01"),
        ("list_guests", {}, "media"),
        ("get_guest_config", {"node": "pve-01", "type": "qemu", "guest_id": "100"}, "memory"),
        ("list_storage", {}, "local-lvm"),
        ("list_recent_tasks", {}, "qmstart"),
    ]
    for name, args, expected in checks:
        result = module.handle_tool(name, args)["content"][0]["text"]
        if expected not in result:
            raise AssertionError(f"{name} result did not include {expected}: {result}")
        if "redact-me" in result:
            raise AssertionError("get_guest_config leaked secret-like config data")


def main() -> int:
    assert_tool_list(
        ROOT / "packages" / "mcp-servers" / "proxmox" / "server.py",
        {"list_nodes", "list_guests", "get_guest_config"},
    )
    assert_tool_list(
        ROOT / "packages" / "mcp-servers" / "docker" / "server.py",
        {
            "list_containers",
            "inspect_container",
            "list_compose_projects",
            "list_volumes",
            "read_container_logs",
            "plan_stack_update",
        },
    )
    assert_tool_list(
        ROOT / "packages" / "mcp-servers" / "networking" / "server.py",
        {"inspect_interfaces", "inspect_dns", "inspect_tailnet", "scan_local_services", "plan_firewall_change"},
    )
    assert_tool_list(
        ROOT / "packages" / "mcp-servers" / "storage-nas" / "server.py",
        {"list_disks", "read_smart_health", "list_pools", "check_backup_freshness", "plan_share_change"},
    )
    assert_tool_list(
        ROOT / "packages" / "mcp-servers" / "monitoring" / "server.py",
        {"list_alerts", "query_metrics", "read_logs", "build_incident_summary"},
    )
    assert_tool_list(
        ROOT / "packages" / "mcp-servers" / "vm-management" / "server.py",
        {"list_vms", "inspect_vm", "plan_snapshot"},
    )
    assert_proxmox_inventory()
    assert_proxmox_api_formatting()
    print("MCP smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
