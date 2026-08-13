#!/usr/bin/env python3
"""Read-only monitoring/diagnostics MCP reference server."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


MAX_OUTPUT_BYTES = 64_000
MAX_LOG_LINES = 200

TOOLS = [
    {"name": "list_alerts", "description": "List configured alert hints from ALERT_URLS health endpoints.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "query_metrics", "description": "Read bounded host metrics from local OS tools.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "read_logs", "description": "Read bounded local logs for an explicit service name.", "inputSchema": {"type": "object", "properties": {"service": {"type": "string"}, "lines": {"type": "integer", "default": 80, "minimum": 1, "maximum": MAX_LOG_LINES}}, "required": ["service"], "additionalProperties": False}},
    {"name": "build_incident_summary", "description": "Build a structured incident triage checklist from supplied symptom text.", "inputSchema": {"type": "object", "properties": {"symptom": {"type": "string"}}, "additionalProperties": False}},
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


def list_alerts(_: dict[str, Any]) -> dict[str, Any]:
    urls = [item for item in os.environ.get("ALERT_URLS", "").split(",") if item.strip()]
    if not urls:
        return text_result("ALERT_URLS is not configured. Set comma-separated health or alert endpoint URLs.")
    lines = ["Configured alert/health endpoint checks:"]
    for url in urls:
        try:
            request = Request(url, method="GET", headers={"User-Agent": "agentic-homelab-monitoring/0.1"})
            with urlopen(request, timeout=5) as response:
                lines.append(f"- {url}: HTTP {response.status}")
        except URLError as exc:
            lines.append(f"- {url}: failed {exc.reason}")
    return text_result("\n".join(lines))


def query_metrics(_: dict[str, Any]) -> dict[str, Any]:
    system = platform.system().lower()
    parts = []
    if system == "darwin":
        parts.extend([run_command(["uptime"]), run_command(["vm_stat"]), run_command(["df", "-h"])])
    elif system == "linux":
        parts.extend([run_command(["uptime"]), run_command(["free", "-h"]), run_command(["df", "-h"])])
    else:
        parts.append(f"Unsupported OS for metrics: {platform.system()}")
    return text_result("\n\n".join(parts))


def read_logs(args: dict[str, Any]) -> dict[str, Any]:
    service = args["service"]
    lines = min(max(int(args.get("lines", 80)), 1), MAX_LOG_LINES)
    system = platform.system().lower()
    if system == "linux" and shutil.which("journalctl"):
        return text_result(run_command(["journalctl", "-u", service, "-n", str(lines), "--no-pager"], timeout=12))
    if system == "darwin" and shutil.which("log"):
        predicate = f'process == "{service}"'
        return text_result(run_command(["log", "show", "--last", "30m", "--style", "compact", "--predicate", predicate], timeout=12))
    return text_result("No supported local log reader found. Configure service-specific log collection.")


def build_incident_summary(args: dict[str, Any]) -> dict[str, Any]:
    symptom = args.get("symptom", "<symptom>")
    return text_result(
        "Incident triage summary template. No remediation was performed.\n"
        f"Symptom: {symptom}\n"
        "1. Scope: which service, node, users, and time window are affected?\n"
        "2. Recent change: deploy, update, reboot, storage/network change, credential change?\n"
        "3. Signals: metrics, logs, health endpoints, Proxmox/Docker task status.\n"
        "4. Hypothesis: most likely cause and confidence.\n"
        "5. Safe next check: one read-only command/tool call.\n"
        "6. Approval needed before: restart, config write, alert silence, firewall/storage change.\n"
        "7. Verifier: exact external signal that proves recovery."
    )


HANDLERS = {
    "list_alerts": list_alerts,
    "query_metrics": query_metrics,
    "read_logs": read_logs,
    "build_incident_summary": build_incident_summary,
}


def handle_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    handler = HANDLERS.get(name)
    if handler:
        return handler(args)
    if name in {"silence_alert", "change_scrape_config"}:
        return text_result(f"{name} is intentionally not implemented in this read-only reference server.")
    return text_result(f"Unknown tool: {name}")


def handle(message: dict[str, Any]) -> None:
    method = message.get("method")
    message_id = message.get("id")
    if method == "initialize":
        respond(message_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "agentic-homelab-monitoring", "version": "0.1.0"}})
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

