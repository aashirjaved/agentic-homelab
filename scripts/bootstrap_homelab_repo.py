#!/usr/bin/env python3
"""Create a starter agent-friendly homelab repository layout."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


STARTER_FILES = [
    ("templates/inventory/homelab.inventory.example.yaml", "homelab.inventory.yaml"),
    ("guardrails/policies/default-policy.yaml", "guardrails/policies/default-policy.yaml"),
    ("guardrails/action-risk-matrix.yaml", "guardrails/action-risk-matrix.yaml"),
    ("templates/agent-instructions/AGENTS.md", "AGENTS.md"),
]


def copy_file(source: Path, destination: Path, force: bool) -> str:
    if destination.exists() and not force:
        return f"skip existing {destination}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return f"write {destination}"


def write_text(path: Path, text: str, force: bool) -> str:
    if path.exists() and not force:
        return f"skip existing {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return f"write {path}"


def starter_readme() -> str:
    return """# Homelab Agent Context

This directory was bootstrapped from `agentic-homelab`.

Start here:

1. Edit `homelab.inventory.yaml` with nodes, services, storage, networks, and
   local agents. Use credential references, not secret values.
2. Review `guardrails/policies/default-policy.yaml`.
3. Review `guardrails/action-risk-matrix.yaml`.
4. Keep `AGENTS.md` updated with local paths and operating rules.
5. Run read-only discovery before approving any change.

Suggested first prompt:

```text
Read AGENTS.md, homelab.inventory.yaml, and guardrails/policies/default-policy.yaml.
Inspect only read-only state for one target I name. Do not make changes.
Return findings, uncertainty, risks, and verifiers for any proposed future change.
```
"""


def maintenance_log() -> str:
    return """# Maintenance Log

Use one entry per maintenance task.

```text
Date:
Operator:
Agent/client:
Scope:
Action:
Approval:
Verifier:
Result:
Follow-up:
```
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Directory to create or update")
    parser.add_argument("--force", action="store_true", help="Overwrite existing starter files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = args.target.expanduser().resolve()
    actions: list[str] = []

    target.mkdir(parents=True, exist_ok=True)
    for source_name, destination_name in STARTER_FILES:
        source = ROOT / source_name
        if not source.exists():
            print(f"missing source template: {source}", file=sys.stderr)
            return 1
        actions.append(copy_file(source, target / destination_name, args.force))

    actions.append(write_text(target / "README.md", starter_readme(), args.force))
    actions.append(write_text(target / "maintenance-log.md", maintenance_log(), args.force))
    actions.append(write_text(target / "diagnostics" / ".gitkeep", "", args.force))

    print(f"Bootstrapped homelab agent starter at {target}")
    for action in actions:
        print(f"- {action}")
    print("\nNext: edit homelab.inventory.yaml and replace placeholders in AGENTS.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
