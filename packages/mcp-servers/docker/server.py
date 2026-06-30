#!/usr/bin/env python3
"""Read-only Docker MCP reference server."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from typing import Any


MAX_LOG_LINES = 120
MAX_OUTPUT_BYTES = 64_000

TOOLS = [
    {
        "name": "list_containers",
        "description": "List Docker containers with status, health, ports, and image.",
        "inputSchema": {
            "type": "object",
            "properties": {"all": {"type": "boolean", "default": True}},
            "additionalProperties": False,
        },
    },
    {
        "name": "inspect_container",
        "description": "Inspect one Docker container by name or id.",
        "inputSchema": {
            "type": "object",
            "properties": {"container": {"type": "string"}},
            "required": ["container"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_compose_projects",
        "description": "List Docker Compose projects visible to Docker.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_volumes",
        "description": "List Docker volumes without deleting or pruning anything.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "read_container_logs",
        "description": "Read bounded recent logs for one container.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "container": {"type": "string"},
                "lines": {"type": "integer", "minimum": 1, "maximum": MAX_LOG_LINES, "default": 80},
            },
            "required": ["container"],
            "additionalProperties": False,
        },
    },
    {
        "name": "plan_stack_update",
        "description": "Create a human-reviewable Docker maintenance plan. Does not pull, restart, or write.",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}},
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


def docker_available() -> str | None:
    docker = shutil.which("docker")
    if not docker:
        return None
    return docker


def run_docker(args: list[str], timeout: int = 10) -> tuple[int, str, str]:
    docker = docker_available()
    if not docker:
        return 127, "", "docker CLI not found on PATH"
    proc = subprocess.run(
        [docker, *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout[:MAX_OUTPUT_BYTES], proc.stderr[:MAX_OUTPUT_BYTES]


def render_command_result(code: int, stdout: str, stderr: str) -> dict[str, Any]:
    if code != 0:
        return text_result(f"Docker command failed with exit code {code}.\n\nstderr:\n{stderr.strip()}")
    return text_result(stdout.strip() or "(no output)")


def list_containers(args: dict[str, Any]) -> dict[str, Any]:
    cmd = ["ps", "--format", "table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"]
    if args.get("all", True):
        cmd.insert(1, "--all")
    return render_command_result(*run_docker(cmd))


def inspect_container(args: dict[str, Any]) -> dict[str, Any]:
    container = args["container"]
    code, stdout, stderr = run_docker(
        [
            "inspect",
            "--format",
            (
                "Name={{.Name}}\n"
                "Image={{.Config.Image}}\n"
                "State={{.State.Status}}\n"
                "Health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}\n"
                "RestartPolicy={{.HostConfig.RestartPolicy.Name}}\n"
                "Mounts={{range .Mounts}}{{.Type}}:{{.Source}}->{{.Destination}} {{end}}\n"
                "Networks={{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}"
            ),
            container,
        ]
    )
    return render_command_result(code, stdout, stderr)


def list_compose_projects(_: dict[str, Any]) -> dict[str, Any]:
    code, stdout, stderr = run_docker(
        ["compose", "ls", "--format", "table {{.Name}}\t{{.Status}}\t{{.ConfigFiles}}"]
    )
    if code != 0 and "docker compose" in stderr.lower():
        return text_result("Docker Compose plugin is not available.")
    return render_command_result(code, stdout, stderr)


def list_volumes(_: dict[str, Any]) -> dict[str, Any]:
    return render_command_result(*run_docker(["volume", "ls"]))


def read_container_logs(args: dict[str, Any]) -> dict[str, Any]:
    lines = min(max(int(args.get("lines", 80)), 1), MAX_LOG_LINES)
    return render_command_result(*run_docker(["logs", "--tail", str(lines), args["container"]], timeout=15))


def plan_stack_update(args: dict[str, Any]) -> dict[str, Any]:
    project = args.get("project", "<project-name>")
    return text_result(
        "Read-only Docker maintenance plan:\n"
        f"1. Confirm project: {project}\n"
        "2. Run list_containers and read_container_logs for unhealthy services.\n"
        "3. Check current image tags and compose file path.\n"
        "4. Before any write, ask for approval with exact commands.\n"
        "5. Suggested approved command shape: docker compose pull && docker compose up -d\n"
        "6. Verifiers: docker ps health, service endpoint, recent logs.\n"
        "\nNo pull, restart, prune, or write was performed."
    )


READ_ONLY_HANDLERS = {
    "list_containers": list_containers,
    "inspect_container": inspect_container,
    "list_compose_projects": list_compose_projects,
    "list_volumes": list_volumes,
    "read_container_logs": read_container_logs,
    "plan_stack_update": plan_stack_update,
}


def handle_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    handler = READ_ONLY_HANDLERS.get(name)
    if handler:
        return handler(args)
    if name in {"apply_stack_update", "prune_resources"}:
        return text_result(f"{name} is intentionally not implemented in this reference server.")
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
                "serverInfo": {"name": "agentic-homelab-docker", "version": "0.1.0"},
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
        except subprocess.TimeoutExpired:
            respond(None, error={"code": -32000, "message": "Docker command timed out"})
        except Exception as exc:  # pragma: no cover - defensive stdio boundary
            respond(None, error={"code": -32000, "message": str(exc)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

