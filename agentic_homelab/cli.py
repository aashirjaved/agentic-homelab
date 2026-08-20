"""Command-line interface for agentic-homelab."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

from . import __version__
from .doctor import (
    DEFAULT_HISTORY,
    build_report,
    create_diagnostic_bundle,
    redact,
    render_changes,
    render_doctor_summary,
    render_investigation,
    render_markdown,
    render_recovery,
    render_updates,
)


def assignment(value: str) -> tuple[str, str]:
    name, separator, target = value.partition("=")
    invalid = (
        not separator or not name or not target
        or any(character.isspace() for character in value)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+", name)
        or target.startswith("-")
    )
    if invalid:
        raise argparse.ArgumentTypeError("expected a safe NODE=VALUE assignment")
    return name, target


def add_evidence_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--inventory", type=Path, help="YAML or JSON inventory that enriches discovery")
    parser.add_argument("--no-discover", action="store_true", help="Use declared inventory only")
    parser.add_argument("--no-local", action="store_true", help="Do not inspect the machine running this command")
    parser.add_argument("--no-remote", action="store_true", help="Do not inspect declared or explicit SSH targets")
    parser.add_argument("--ssh", action="append", type=assignment, default=[], metavar="NODE=DESTINATION",
                        help="Inspect a host over non-interactive SSH; may be repeated")
    parser.add_argument("--ssh-identity", type=Path, help="Identity file used for SSH discovery")
    parser.add_argument("--ssh-host-key-alias", action="append", type=assignment, default=[], metavar="NODE=ALIAS",
                        help="Known-host alias for an SSH target; may be repeated")
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY, help="Observation history path")
    parser.add_argument("--no-history", action="store_true", help="Do not read or write observation history")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="homelab", description="Explain a homelab from read-only evidence.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    doctor = subparsers.add_parser("doctor", help="Discover topology, risks, recovery evidence, and changes")
    add_evidence_options(doctor)
    doctor.add_argument("--full", action="store_true", help="Render the complete report instead of the action brief")
    doctor.add_argument("--share", type=Path, help="Write a redacted Markdown report")

    investigate = subparsers.add_parser("investigate", help="Rank deterministic incident hypotheses")
    investigate.add_argument("component", help="Service or component ID")
    add_evidence_options(investigate)

    changes = subparsers.add_parser("changes", help="Show observed change history")
    add_evidence_options(changes)

    recovery = subparsers.add_parser("recovery", help="Assess declared and observed recovery evidence")
    add_evidence_options(recovery)

    updates = subparsers.add_parser("updates", help="Assess update readiness from supplied metadata")
    updates.add_argument("service", nargs="?", help="Optional service ID")
    add_evidence_options(updates)

    share = subparsers.add_parser("share", help="Create a redacted diagnostic bundle")
    share.add_argument("output", type=Path, help="Empty output directory")
    share.add_argument("--investigate", metavar="COMPONENT", help="Include incident hypotheses")
    add_evidence_options(share)
    return parser


def report_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "inventory_path": args.inventory,
        "discover": not args.no_discover,
        "discover_local_host": not args.no_local,
        "discover_remote": not args.no_remote,
        "ssh_targets": dict(args.ssh),
        "ssh_identity": args.ssh_identity,
        "ssh_host_key_aliases": dict(args.ssh_host_key_alias),
        "history_path": args.history,
        "use_history": not args.no_history,
    }


def json_view(report: dict[str, Any], command: str) -> Any:
    keys = {
        "investigate": "investigation",
        "changes": "timeline",
        "recovery": "recovery_readiness",
        "updates": "update_intelligence",
    }
    return report if command == "doctor" else report.get(keys[command])


def render_view(report: dict[str, Any], command: str) -> str:
    renderers = {
        "doctor": render_markdown,
        "investigate": render_investigation,
        "changes": render_changes,
        "recovery": render_recovery,
        "updates": render_updates,
    }
    return renderers[command](report)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    kwargs = report_kwargs(args)
    kwargs["include_recovery_findings"] = args.command == "recovery"
    if args.command == "investigate":
        kwargs["investigate_target"] = args.component
    elif args.command == "updates":
        kwargs["include_updates"] = True
        kwargs["update_target"] = args.service
    elif args.command == "share":
        kwargs["investigate_target"] = args.investigate

    report = build_report(**kwargs)
    if args.command == "share":
        try:
            files = create_diagnostic_bundle(report, args.output)
        except ValueError as exc:
            print(f"homelab share: {exc}", file=sys.stderr)
            return 2
        print(f"Diagnostic bundle written to {args.output} ({', '.join(files)})")
        return 0

    if args.format == "json":
        print(json.dumps(json_view(report, args.command), indent=2, sort_keys=True))
    else:
        if args.command == "doctor" and not args.full:
            print(render_doctor_summary(report), end="")
        else:
            print(render_view(report, args.command), end="")
    if args.command == "doctor" and args.share:
        args.share.parent.mkdir(parents=True, exist_ok=True)
        args.share.write_text(redact(render_markdown(report, shared=True)), encoding="utf-8")
        print(f"Shareable report written to {args.share}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
