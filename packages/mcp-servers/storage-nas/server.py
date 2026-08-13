#!/usr/bin/env python3
"""Read-only storage/NAS MCP reference server."""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from typing import Any


MAX_OUTPUT_BYTES = 64_000

TOOLS = [
    {"name": "list_disks", "description": "List disks using local OS tools.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "read_smart_health", "description": "Read SMART health if smartctl is installed.", "inputSchema": {"type": "object", "properties": {"device": {"type": "string"}}, "additionalProperties": False}},
    {"name": "list_pools", "description": "List filesystems, mounts, and ZFS pools if available.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "check_backup_freshness", "description": "Check freshness of configured BACKUP_PATHS only.", "inputSchema": {"type": "object", "properties": {"max_age_hours": {"type": "integer", "default": 24}}, "additionalProperties": False}},
    {"name": "plan_share_change", "description": "Prepare a storage/share change plan without applying it.", "inputSchema": {"type": "object", "properties": {"share": {"type": "string"}}, "additionalProperties": False}},
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


def list_disks(_: dict[str, Any]) -> dict[str, Any]:
    system = platform.system().lower()
    if system == "darwin":
        parts = [run_command(["diskutil", "list"])]
    elif system == "linux":
        parts = [run_command(["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,SERIAL"])]
    else:
        parts = [f"Unsupported OS for disk listing: {platform.system()}"]
    return text_result("\n\n".join(parts))


def read_smart_health(args: dict[str, Any]) -> dict[str, Any]:
    if not shutil.which("smartctl"):
        return text_result("smartctl not found. Install smartmontools on the host to read SMART health.")
    device = args.get("device")
    if not device:
        return text_result("Provide a device path, for example /dev/sda or /dev/nvme0n1.")
    return text_result(run_command(["smartctl", "-H", device]))


def list_pools(_: dict[str, Any]) -> dict[str, Any]:
    parts = []
    if platform.system().lower() == "linux":
        parts.append(run_command(["findmnt", "-D"]))
    else:
        parts.append(run_command(["mount"]))
    if shutil.which("zpool"):
        parts.append(run_command(["zpool", "status"]))
        parts.append(run_command(["zfs", "list"]))
    return text_result("\n\n".join(parts))


def check_backup_freshness(args: dict[str, Any]) -> dict[str, Any]:
    max_age_hours = int(args.get("max_age_hours", 24))
    raw_paths = os.environ.get("BACKUP_PATHS", "")
    paths = [Path(item).expanduser() for item in raw_paths.split(":") if item.strip()]
    if not paths:
        return text_result("BACKUP_PATHS is not configured. Set colon-separated paths to check backup freshness.")
    now = time.time()
    lines = [f"Backup freshness threshold: {max_age_hours}h"]
    for path in paths:
        if not path.exists():
            lines.append(f"- {path}: missing")
            continue
        newest = max((item.stat().st_mtime for item in path.rglob("*") if item.is_file()), default=path.stat().st_mtime)
        age_hours = (now - newest) / 3600
        status = "fresh" if age_hours <= max_age_hours else "stale"
        lines.append(f"- {path}: {status}, newest file age {age_hours:.1f}h")
    return text_result("\n".join(lines))


def plan_share_change(args: dict[str, Any]) -> dict[str, Any]:
    share = args.get("share", "<share>")
    return text_result(
        "Storage/share change plan only. No change was made.\n"
        f"Share: {share}\n"
        "Before approval:\n"
        "- identify owning service and clients\n"
        "- verify backup freshness and restore path\n"
        "- state exact config file or API target\n"
        "- define rollback\n"
        "- verify mount/share access after change"
    )


HANDLERS = {
    "list_disks": list_disks,
    "read_smart_health": read_smart_health,
    "list_pools": list_pools,
    "check_backup_freshness": check_backup_freshness,
    "plan_share_change": plan_share_change,
}


def handle_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    handler = HANDLERS.get(name)
    if handler:
        return handler(args)
    if name in {"apply_share_change", "format_disk"}:
        return text_result(f"{name} is intentionally not implemented in this read-only reference server.")
    return text_result(f"Unknown tool: {name}")


def handle(message: dict[str, Any]) -> None:
    method = message.get("method")
    message_id = message.get("id")
    if method == "initialize":
        respond(message_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "agentic-homelab-storage-nas", "version": "0.1.0"}})
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

