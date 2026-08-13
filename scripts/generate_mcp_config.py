#!/usr/bin/env python3
"""Generate MCP client configuration for agentic-homelab reference servers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_NAMES = {
    "proxmox": "agentic-homelab-proxmox",
    "docker": "agentic-homelab-docker",
    "networking": "agentic-homelab-networking",
    "storage-nas": "agentic-homelab-storage",
    "monitoring": "agentic-homelab-monitoring",
    "vm-management": "agentic-homelab-vm-management",
}


def server_config(server_id: str, inventory: Path | None, extra_env: dict[str, str]) -> dict[str, object]:
    server_path = ROOT / "packages" / "mcp-servers" / server_id / "server.py"
    env: dict[str, str] = {}
    if inventory and server_id in {"proxmox", "vm-management"}:
        env["AGENTIC_HOMELAB_INVENTORY"] = str(inventory.resolve())
    if server_id == "proxmox":
        # Desktop MCP clients launch servers with their own environment, not the
        # user's shell, so credentials must be baked into the config env block.
        env.update({k: v for k, v in extra_env.items() if k.startswith("PROXMOX_")})
    return {
        "command": "python3",
        "args": [str(server_path.resolve())],
        "env": env,
    }


def generate(servers: list[str], inventory: Path | None, extra_env: dict[str, str]) -> dict[str, object]:
    return {
        "mcpServers": {
            SERVER_NAMES[server_id]: server_config(server_id, inventory, extra_env)
            for server_id in servers
        }
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--servers",
        default=",".join(SERVER_NAMES),
        help="Comma-separated server ids to include",
    )
    parser.add_argument("--inventory", type=Path, help="Optional inventory path for inventory-aware servers")
    parser.add_argument("--output", type=Path, help="Optional output file. Defaults to stdout.")
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Environment entry for the generated config, repeatable. "
        "PROXMOX_* keys are attached to the proxmox server (required for live "
        "API access from desktop MCP clients, which do not inherit your shell env).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    servers = [item.strip() for item in args.servers.split(",") if item.strip()]
    unknown = [server for server in servers if server not in SERVER_NAMES]
    if unknown:
        raise SystemExit(f"Unknown server ids: {', '.join(unknown)}")
    extra_env: dict[str, str] = {}
    for item in args.env:
        if "=" not in item:
            raise SystemExit(f"--env expects KEY=VALUE, got: {item}")
        key, value = item.split("=", 1)
        extra_env[key] = value
    config = generate(servers, args.inventory, extra_env)
    text = json.dumps(config, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

