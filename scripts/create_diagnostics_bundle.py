#!/usr/bin/env python3
"""Create a redacted diagnostics bundle for agent-assisted homelab debugging."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "diagnostics" / time.strftime("%Y%m%d-%H%M%S")
MAX_OUTPUT_BYTES = 64_000
SECRET_WORDS = ("password", "secret", "token", "key", "cookie", "session")


def safe_env_names() -> list[str]:
    names = []
    for name in sorted(os.environ):
        lowered = name.lower()
        if any(word in lowered for word in SECRET_WORDS):
            names.append(f"{name}=<redacted>")
        elif name.startswith(("AGENTIC_HOMELAB_", "PROXMOX_", "BACKUP_", "ALERT_")):
            names.append(f"{name}=<set>")
    return names


def run_command(args: list[str], timeout: int = 8) -> str:
    if not shutil.which(args[0]):
        return f"{args[0]} not found\n"
    try:
        proc = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"$ {' '.join(args)}\ncommand timed out\n"
    body = proc.stdout if proc.returncode == 0 else proc.stderr
    return f"$ {' '.join(args)}\nexit={proc.returncode}\n{body[:MAX_OUTPUT_BYTES]}\n"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_inventory(bundle: Path, inventory: Path | None) -> str:
    if not inventory:
        return "not provided"
    if not inventory.exists():
        return f"missing: {inventory}"
    target = bundle / "inventory" / inventory.name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(inventory.read_text(encoding="utf-8")[:MAX_OUTPUT_BYTES], encoding="utf-8")
    return str(target.relative_to(bundle))


def command_set() -> dict[str, list[list[str]]]:
    system = platform.system().lower()
    common = {
        "system": [["uname", "-a"], ["uptime"], ["df", "-h"]],
        "network": [],
        "storage": [],
    }
    if system == "darwin":
        common["network"] = [["ifconfig"], ["netstat", "-rn", "-f", "inet"]]
        common["storage"] = [["diskutil", "list"], ["mount"]]
    elif system == "linux":
        common["system"].append(["free", "-h"])
        common["network"] = [["ip", "addr"], ["ip", "route"]]
        common["storage"] = [["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL"], ["findmnt", "-D"]]
    return common


def collect_commands(bundle: Path, include_commands: bool) -> list[str]:
    if not include_commands:
        return []
    written = []
    for group, commands in command_set().items():
        chunks = [run_command(command) for command in commands]
        target = bundle / "commands" / f"{group}.txt"
        write_text(target, "\n".join(chunks))
        written.append(str(target.relative_to(bundle)))
    return written


def create_bundle(output: Path, inventory: Path | None, include_commands: bool) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    inventory_status = copy_inventory(output, inventory)
    command_files = collect_commands(output, include_commands)

    manifest = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host_os": platform.platform(),
        "inventory": inventory_status,
        "command_files": command_files,
        "redaction": "environment values are not included; secret-like env names are marked redacted",
    }
    write_text(output / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    write_text(output / "env-names.txt", "\n".join(safe_env_names()) + "\n")
    write_text(
        output / "redactions.txt",
        "Excluded by design:\n"
        "- raw environment values\n"
        "- private keys\n"
        "- API tokens\n"
        "- passwords\n"
        "- cookies/session values\n"
        "- arbitrary user files\n",
    )
    write_text(
        output / "README.md",
        "# Diagnostics Bundle\n\n"
        "This bundle is intended for agent-assisted debugging. It should contain observed state, not secrets.\n\n"
        "Start with `manifest.json`, then inspect command outputs and inventory if present.\n",
    )
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Bundle output directory")
    parser.add_argument("--inventory", type=Path, help="Optional inventory file to copy into the bundle")
    parser.add_argument(
        "--include-commands",
        action="store_true",
        help="Collect bounded read-only local command output",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle = create_bundle(args.output, args.inventory, args.include_commands)
    print(bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

