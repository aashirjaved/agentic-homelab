#!/usr/bin/env python3
"""Read-only networking MCP reference server."""

from __future__ import annotations

import json
import platform
import shutil
import socket
import subprocess
import sys
from typing import Any


MAX_OUTPUT_BYTES = 64_000
LOCAL_PORTS = [22, 80, 443, 8006, 8096, 3000, 5000, 5432, 6379, 8080]

TOOLS = [
    {
        "name": "inspect_interfaces",
        "description": "Read interface addresses and routes using local OS tools.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "inspect_dns",
        "description": "Inspect resolver configuration and a bounded lookup.",
        "inputSchema": {
            "type": "object",
            "properties": {"host": {"type": "string", "default": "example.com"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "inspect_tailnet",
        "description": "Read Tailscale status if the tailscale CLI is installed.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "scan_local_services",
        "description": "Check a small allowlisted set of local ports on 127.0.0.1 only.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "plan_firewall_change",
        "description": "Prepare a firewall change checklist. Does not modify firewall state.",
        "inputSchema": {
            "type": "object",
            "properties": {"service": {"type": "string"}, "port": {"type": "integer"}},
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


def run_command(args: list[str], timeout: int = 8) -> str:
    if not shutil.which(args[0]):
        return f"{args[0]} not found"
    proc = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        return f"$ {' '.join(args)}\nexit={proc.returncode}\n{proc.stderr.strip()}"
    return f"$ {' '.join(args)}\n{proc.stdout.strip()}"


def inspect_interfaces(_: dict[str, Any]) -> dict[str, Any]:
    system = platform.system().lower()
    if system == "darwin":
        parts = [run_command(["ifconfig"]), run_command(["netstat", "-rn", "-f", "inet"])]
    elif system == "linux":
        parts = [run_command(["ip", "addr"]), run_command(["ip", "route"])]
    else:
        parts = [f"Unsupported OS for detailed interface inspection: {platform.system()}"]
    return text_result("\n\n".join(parts))


def inspect_dns(args: dict[str, Any]) -> dict[str, Any]:
    host = args.get("host", "example.com")
    lines = [f"Resolver lookup for {host}:"]
    try:
        for family, _, _, _, sockaddr in socket.getaddrinfo(host, None):
            lines.append(f"- {socket.AddressFamily(family).name}: {sockaddr[0]}")
    except socket.gaierror as exc:
        lines.append(f"- lookup failed: {exc}")
    if platform.system().lower() == "darwin":
        lines.append(run_command(["scutil", "--dns"]))
    elif platform.system().lower() == "linux":
        lines.append(run_command(["resolvectl", "status"]))
    return text_result("\n".join(lines))


def inspect_tailnet(_: dict[str, Any]) -> dict[str, Any]:
    if not shutil.which("tailscale"):
        return text_result("tailscale CLI not found. Tailnet status unavailable.")
    return text_result(run_command(["tailscale", "status"], timeout=10))


def scan_local_services(_: dict[str, Any]) -> dict[str, Any]:
    lines = ["Local-only port check on 127.0.0.1:"]
    for port in LOCAL_PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            open_ = sock.connect_ex(("127.0.0.1", port)) == 0
        lines.append(f"- {port}: {'open' if open_ else 'closed'}")
    return text_result("\n".join(lines))


def plan_firewall_change(args: dict[str, Any]) -> dict[str, Any]:
    service = args.get("service", "<service>")
    port = args.get("port", "<port>")
    return text_result(
        "Firewall change plan only. No change was made.\n"
        f"Service: {service}\n"
        f"Port: {port}\n"
        "Required before approval:\n"
        "- confirm exposure scope: LAN, tailnet, VPN, or public internet\n"
        "- confirm authentication on the service\n"
        "- confirm rollback command\n"
        "- verify with local port check and external/tailnet reachability as applicable"
    )


HANDLERS = {
    "inspect_interfaces": inspect_interfaces,
    "inspect_dns": inspect_dns,
    "inspect_tailnet": inspect_tailnet,
    "scan_local_services": scan_local_services,
    "plan_firewall_change": plan_firewall_change,
}


def handle_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    handler = HANDLERS.get(name)
    if handler:
        return handler(args)
    if name in {"apply_firewall_change", "expose_service"}:
        return text_result(f"{name} is intentionally not implemented in this read-only reference server.")
    return text_result(f"Unknown tool: {name}")


def handle(message: dict[str, Any]) -> None:
    method = message.get("method")
    message_id = message.get("id")
    if method == "initialize":
        respond(message_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "agentic-homelab-networking", "version": "0.1.0"}})
    elif method == "tools/list":
        respond(message_id, {"tools": TOOLS})
    elif method == "tools/call":
        params = message.get("params", {})
        try:
            respond(message_id, handle_tool(params.get("name", ""), params.get("arguments", {})))
        except Exception as exc:  # keep the request id so clients can correlate the failure
            respond(
                message_id,
                {"content": [{"type": "text", "text": f"Tool call failed: {exc}"}], "isError": True},
            )
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

