"""Command-line interface for agentic-homelab."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .doctor import main as doctor_main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homelab",
        description="Explain a homelab from read-only evidence.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    doctor = subparsers.add_parser("doctor", help="Discover topology, risks, recovery evidence, and changes")
    doctor.add_argument("args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

    investigate = subparsers.add_parser("investigate", help="Rank deterministic incident hypotheses")
    investigate.add_argument("component", help="Service or component ID to investigate")
    investigate.add_argument("args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

    changes = subparsers.add_parser("changes", help="Show the current report with observed change history")
    changes.add_argument("args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

    recovery = subparsers.add_parser("recovery", help="Assess declared and observed recovery evidence")
    recovery.add_argument("args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

    updates = subparsers.add_parser("updates", help="Assess update readiness from supplied metadata")
    updates.add_argument("service", nargs="?", help="Optional service ID")
    updates.add_argument("args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

    share = subparsers.add_parser("share", help="Create a redacted diagnostic bundle")
    share.add_argument("output", help="Empty output directory")
    share.add_argument("args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not argv:
        parser.print_help()
        return 0
    command, trailing = argv[0], argv[1:]
    if command in {"-h", "--help", "--version"}:
        parser.parse_args([command])
        return 0
    if command in {"doctor", "changes", "recovery"}:
        return doctor_main(trailing)
    if command == "investigate":
        if not trailing or trailing[0].startswith("-"):
            parser.error("investigate requires a component")
        return doctor_main(["--investigate", trailing[0], *trailing[1:]])
    if command == "updates":
        update_args = ["--plan-updates"]
        if trailing and not trailing[0].startswith("-"):
            update_args.append(trailing.pop(0))
        return doctor_main([*update_args, *trailing])
    if command == "share":
        if not trailing or trailing[0].startswith("-"):
            parser.error("share requires an output directory")
        return doctor_main(["--bundle", trailing[0], *trailing[1:]])
    parser.error(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
