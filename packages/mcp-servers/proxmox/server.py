#!/usr/bin/env python3
"""Minimal read-only Proxmox MCP reference server.

This intentionally starts conservative. It speaks enough JSON-RPC over stdio
for MCP clients to discover tools, and it refuses write operations.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import ssl
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


TOOLS = [
    {
        "name": "list_nodes",
        "description": "List Proxmox nodes from API when configured, otherwise JSON inventory.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_guests",
        "description": "List VMs and containers through the read-only Proxmox API.",
        "inputSchema": {
            "type": "object",
            "properties": {"node": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_guest_config",
        "description": "Inspect VM or container config through the read-only Proxmox API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {"type": "string"},
                "guest_id": {"type": "string"},
                "type": {"type": "string", "enum": ["qemu", "lxc"]},
            },
            "required": ["node", "guest_id", "type"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_storage",
        "description": "List Proxmox storage through the read-only Proxmox API.",
        "inputSchema": {
            "type": "object",
            "properties": {"node": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "list_recent_tasks",
        "description": "List recent Proxmox tasks through the read-only Proxmox API.",
        "inputSchema": {
            "type": "object",
            "properties": {"node": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}},
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
    return {"content": [{"type": "text", "text": text}]}


def api_configured() -> bool:
    return all(
        os.environ.get(name)
        for name in [
            "PROXMOX_API_URL",
            "PROXMOX_API_TOKEN_ID",
            "PROXMOX_API_TOKEN_SECRET",
        ]
    )


def api_missing_message() -> str:
    return (
        "Proxmox API is not configured. Set PROXMOX_API_URL, "
        "PROXMOX_API_TOKEN_ID, and PROXMOX_API_TOKEN_SECRET for read-only API discovery. "
        "No Proxmox API call was made."
    )


def proxmox_get(path: str) -> dict[str, Any]:
    base_url = os.environ["PROXMOX_API_URL"].rstrip("/")
    token_id = os.environ["PROXMOX_API_TOKEN_ID"]
    token_secret = os.environ["PROXMOX_API_TOKEN_SECRET"]
    verify_tls = os.environ.get("PROXMOX_VERIFY_TLS", "true").lower() not in {"0", "false", "no"}
    timeout = int(os.environ.get("PROXMOX_API_TIMEOUT_SECONDS", "10"))

    context = None if verify_tls else ssl._create_unverified_context()
    request = Request(
        f"{base_url}/api2/json{path}",
        headers={"Authorization": f"PVEAPIToken={token_id}={token_secret}"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Proxmox API HTTP {exc.code}: {body[:1000]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Proxmox API connection failed: {exc.reason}") from exc


def api_data(path: str) -> list[dict[str, Any]] | dict[str, Any]:
    body = proxmox_get(path)
    data = body.get("data")
    if data is None:
        raise RuntimeError(f"Proxmox API response missing data for {path}")
    return data


def compact_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return "(none)"
    rendered = ["\t".join(label for label, _ in columns)]
    for row in rows:
        rendered.append("\t".join(str(row.get(key, "")) for _, key in columns))
    return "\n".join(rendered)


def load_json_inventory() -> tuple[dict[str, Any] | None, str]:
    inventory = Path(os.environ.get("AGENTIC_HOMELAB_INVENTORY", "homelab.inventory.json"))
    if not inventory.exists():
        return None, f"Inventory file not found: {inventory}"
    if inventory.suffix.lower() not in {".json"}:
        return None, (
            f"Inventory file is not JSON: {inventory}. "
            "This dependency-light reference server reads JSON inventory only. "
            "Convert your YAML inventory to JSON or implement YAML parsing."
        )
    try:
        return json.loads(inventory.read_text(encoding="utf-8")), f"Loaded inventory: {inventory}"
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON inventory {inventory}: {exc}"


def list_nodes_from_inventory() -> dict[str, Any]:
    data, status = load_json_inventory()
    if not data:
        return text_result(
            "Read-only Proxmox MCP reference server is running.\n"
            f"{status}\n"
            "Set AGENTIC_HOMELAB_INVENTORY to a JSON inventory file to list nodes.\n"
            "No Proxmox API call was made."
        )

    nodes = [
        node
        for node in data.get("nodes", [])
        if "proxmox" in str(node.get("role", "")).lower() or "pve" in str(node.get("role", "")).lower()
    ]
    if not nodes:
        return text_result(f"{status}\nNo Proxmox nodes found in inventory.")

    lines = [status, "", "Proxmox nodes:"]
    for node in nodes:
        lines.append(
            "- "
            + str(node.get("id", "<missing-id>"))
            + f" role={node.get('role', 'unknown')}"
            + f" address={node.get('address', 'unknown')}"
        )
    return text_result("\n".join(lines))


def list_nodes_from_api() -> dict[str, Any]:
    rows = api_data("/nodes")
    assert isinstance(rows, list)
    return text_result(
        compact_table(
            rows,
            [
                ("node", "node"),
                ("status", "status"),
                ("cpu", "cpu"),
                ("memory", "mem"),
                ("uptime", "uptime"),
            ],
        )
    )


def list_guests_from_api(args: dict[str, Any]) -> dict[str, Any]:
    node = args.get("node")
    if node:
        rows = []
        for guest_type in ["qemu", "lxc"]:
            data = api_data(f"/nodes/{quote(node)}/{guest_type}")
            assert isinstance(data, list)
            for item in data:
                item = dict(item)
                item["type"] = guest_type
                item["node"] = node
                rows.append(item)
    else:
        rows = api_data("/cluster/resources?type=vm")
        assert isinstance(rows, list)
    return text_result(
        compact_table(
            rows,
            [
                ("node", "node"),
                ("type", "type"),
                ("vmid", "vmid"),
                ("name", "name"),
                ("status", "status"),
                ("cpu", "cpu"),
                ("memory", "mem"),
            ],
        )
    )


def get_guest_config_from_api(args: dict[str, Any]) -> dict[str, Any]:
    node = quote(args["node"])
    guest_id = quote(str(args["guest_id"]))
    guest_type = args["type"]
    data = api_data(f"/nodes/{node}/{guest_type}/{guest_id}/config")
    assert isinstance(data, dict)
    redacted = {
        key: value
        for key, value in data.items()
        if "password" not in key.lower() and "secret" not in key.lower() and "token" not in key.lower()
    }
    return text_result(json.dumps(redacted, indent=2, sort_keys=True))


def list_storage_from_api(args: dict[str, Any]) -> dict[str, Any]:
    node = args.get("node")
    path = f"/nodes/{quote(node)}/storage" if node else "/storage"
    rows = api_data(path)
    assert isinstance(rows, list)
    return text_result(
        compact_table(
            rows,
            [
                ("storage", "storage"),
                ("type", "type"),
                ("enabled", "enabled"),
                ("active", "active"),
                ("content", "content"),
            ],
        )
    )


def list_recent_tasks_from_api(args: dict[str, Any]) -> dict[str, Any]:
    limit = min(max(int(args.get("limit", 20)), 1), 50)
    node = args.get("node")
    if node:
        rows = api_data(f"/nodes/{quote(node)}/tasks?limit={limit}")
    else:
        rows = api_data(f"/cluster/tasks?limit={limit}")
    assert isinstance(rows, list)
    return text_result(
        compact_table(
            rows,
            [
                ("node", "node"),
                ("upid", "upid"),
                ("type", "type"),
                ("status", "status"),
                ("user", "user"),
            ],
        )
    )


def handle_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "list_nodes":
        if api_configured():
            return list_nodes_from_api()
        return list_nodes_from_inventory()
    if name == "list_guests":
        if api_configured():
            return list_guests_from_api(args)
        return text_result(api_missing_message())
    if name == "get_guest_config":
        if api_configured():
            return get_guest_config_from_api(args)
        return text_result(api_missing_message())
    if name == "list_storage":
        if api_configured():
            return list_storage_from_api(args)
        return text_result(api_missing_message())
    if name == "list_recent_tasks":
        if api_configured():
            return list_recent_tasks_from_api(args)
        return text_result(api_missing_message())
    if name in {"apply_guest_change", "power_guest", "delete_guest"}:
        return text_result(f"{name} is intentionally not implemented in this read-only reference server.")
    return text_result(f"Unknown tool: {name}")


def handle(message: dict[str, Any]) -> None:
    method = message.get("method")
    message_id = message.get("id")

    if method == "initialize":
        respond(
            message_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agentic-homelab-proxmox", "version": "0.1.0"},
            },
        )
        return

    if method == "tools/list":
        respond(message_id, {"tools": TOOLS})
        return

    if method == "tools/call":
        params = message.get("params", {})
        respond(message_id, handle_tool(params.get("name", ""), params.get("arguments", {})))
        return

    if method == "notifications/initialized":
        return

    respond(message_id, error={"code": -32601, "message": f"Method not found: {method}"})


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            handle(json.loads(line))
        except Exception as exc:  # pragma: no cover - defensive stdio server boundary
            respond(None, error={"code": -32000, "message": str(exc)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
