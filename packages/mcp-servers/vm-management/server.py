#!/usr/bin/env python3
"""Read-only VM management MCP reference server."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


MAX_OUTPUT_BYTES = 64_000

TOOLS = [
    {
        "name": "list_vms",
        "description": "List VMs from libvirt if available and from JSON inventory hints.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "inspect_vm",
        "description": "Inspect one VM through libvirt when available.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "plan_snapshot",
        "description": "Prepare a snapshot plan without creating a snapshot.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
]


def respond(message_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": message_id}
    if error:
        payload["error"] = error
    else:
        payload["result"] = result
    print(json.dumps(payload), flush=True)


def text_result(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text[:MAX_OUTPUT_BYTES]}]}


def run_command(args: list[str], timeout: int = 10) -> str:
    if not shutil.which(args[0]):
        return f"{args[0]} not found"
    proc = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        return f"$ {' '.join(args)}\nexit={proc.returncode}\n{proc.stderr.strip()}"
    return f"$ {' '.join(args)}\n{proc.stdout.strip()}"


def inventory_vms() -> str:
    inventory = Path(os.environ.get("AGENTIC_HOMELAB_INVENTORY", "homelab.inventory.json"))
    if not inventory.exists() or inventory.suffix.lower() != ".json":
        return f"Inventory VM hints unavailable. Set AGENTIC_HOMELAB_INVENTORY to a JSON inventory. Current path: {inventory}"
    try:
        data = json.loads(inventory.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"Inventory JSON parse failed: {exc}"
    services = data.get("services", [])
    lines = ["Inventory service placement hints:"]
    for service in services:
        runs_on = service.get("runs_on", "unknown")
        lines.append(f"- {service.get('id', '<service>')} kind={service.get('kind', 'unknown')} runs_on={runs_on}")
    return "\n".join(lines) if len(lines) > 1 else "No service placement hints found in inventory."


def list_vms(_: dict[str, Any]) -> dict[str, Any]:
    parts = [inventory_vms()]
    if shutil.which("virsh"):
        parts.append(run_command(["virsh", "list", "--all"]))
    else:
        parts.append("virsh not found. Libvirt VM inventory unavailable.")
    return text_result("\n\n".join(parts))


def inspect_vm(args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    if not shutil.which("virsh"):
        return text_result("virsh not found. Cannot inspect local libvirt VM.")
    return text_result(
        "\n\n".join(
            [
                run_command(["virsh", "dominfo", name]),
                run_command(["virsh", "domblklist", name]),
                run_command(["virsh", "domiflist", name]),
            ]
        )
    )


def plan_snapshot(args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    reason = args.get("reason", "<reason>")
    return text_result(
        "Snapshot plan only. No snapshot was created.\n"
        f"VM: {name}\n"
        f"Reason: {reason}\n"
        "Before approval:\n"
        "- confirm provider: Proxmox, libvirt, or other\n"
        "- verify VM state and disk usage\n"
        "- verify storage has enough free space\n"
        "- state exact snapshot command/API call\n"
        "- define retention and delete plan\n"
        "- verifier: snapshot appears in provider and VM remains healthy"
    )


HANDLERS = {"list_vms": list_vms, "inspect_vm": inspect_vm, "plan_snapshot": plan_snapshot}


def handle_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    handler = HANDLERS.get(name)
    if handler:
        return handler(args)
    if name in {"create_snapshot", "resize_vm", "delete_snapshot"}:
        return text_result(f"{name} is intentionally not implemented in this read-only reference server.")
    return text_result(f"Unknown tool: {name}")


def handle(message: dict[str, Any]) -> None:
    method = message.get("method")
    message_id = message.get("id")
    if method == "initialize":
        respond(message_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "agentic-homelab-vm-management", "version": "0.1.0"}})
    elif method == "tools/list":
        respond(message_id, {"tools": TOOLS})
    elif method == "tools/call":
        params = message.get("params", {})
        respond(message_id, handle_tool(params.get("name", ""), params.get("arguments", {})))
    elif method == "notifications/initialized":
        return
    else:
        respond(message_id, error={"code": -32601, "message": f"Method not found: {method}"})


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            handle(json.loads(line))
        except subprocess.TimeoutExpired:
            respond(None, error={"code": -32000, "message": "Command timed out"})
        except Exception as exc:
            respond(None, error={"code": -32000, "message": str(exc)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

