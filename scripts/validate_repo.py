#!/usr/bin/env python3
"""Lightweight repository validator for agentic-homelab."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - user-facing fallback
    raise SystemExit("Missing PyYAML. Install with: python3 -m pip install pyyaml") from exc

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover - user-facing fallback
    raise SystemExit("Missing jsonschema. Install with: python3 -m pip install jsonschema") from exc


ROOT = Path(__file__).resolve().parents[1]
RISKS_REQUIRING_APPROVAL = {"write", "destructive", "credential-access"}
GENERIC_APPROVAL_LABELS = {
    "firewall changes",
    "service restarts",
    "storage changes",
    "credential access",
    "public exposure",
}
SECRET_PATTERNS = [
    "password=",
    "BEGIN PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "api_key=",
    "token=",
]


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_json_schema(errors: list[str], data: Any, schema_name: str, target: Path) -> None:
    schema_path = ROOT / "schemas" / schema_name
    schema = load_json(schema_path)
    validator = jsonschema.Draft202012Validator(schema)
    schema_errors = sorted(validator.iter_errors(data), key=lambda item: list(item.path))
    for error in schema_errors:
        location = ".".join(str(part) for part in error.path) or "<root>"
        fail(errors, f"{target}: schema {schema_name} failed at {location}: {error.message}")


def validate_mcp_manifests(errors: list[str]) -> None:
    manifests = sorted((ROOT / "packages" / "mcp-servers").glob("*/mcp.yaml"))
    if not manifests:
        fail(errors, "No MCP manifests found under packages/mcp-servers/*/mcp.yaml")
        return

    for path in manifests:
        data = load_yaml(path)
        validate_json_schema(errors, data, "mcp-server.schema.json", path)
        for key in ["id", "name", "status", "transport", "risk_default", "tools"]:
            if key not in data:
                fail(errors, f"{path}: missing required key {key}")
        for tool in data.get("tools", []):
            risk = tool.get("risk")
            name = tool.get("name", "<unnamed>")
            if risk in RISKS_REQUIRING_APPROVAL and not tool.get("requires_approval"):
                fail(errors, f"{path}: tool {name} has risk={risk} but requires_approval is not true")
        readme_path = path.parent / "README.md"
        if not readme_path.exists():
            fail(errors, f"{path.parent}: missing README.md")
            continue
        readme = readme_path.read_text(encoding="utf-8")
        for heading in ["Implemented Read-Only Tools", "Smoke Test", "Configuration", "Safety Contract"]:
            if heading not in readme:
                fail(errors, f"{readme_path}: missing README section {heading}")


def mcp_tool_index() -> tuple[dict[str, set[str]], set[str]]:
    tools_by_server: dict[str, set[str]] = {}
    server_ids: set[str] = set()
    for path in sorted((ROOT / "packages" / "mcp-servers").glob("*/mcp.yaml")):
        data = load_yaml(path)
        server_id = data["id"]
        server_ids.add(server_id)
        tools_by_server[server_id] = {tool["name"] for tool in data.get("tools", [])}
    return tools_by_server, server_ids


def skill_ids() -> set[str]:
    return {path.name for path in (ROOT / "skills").iterdir() if path.is_dir()}


def validate_skill_metadata(errors: list[str]) -> None:
    for path in sorted(item for item in (ROOT / "skills").iterdir() if item.is_dir()):
        required_paths = [
            path / "SKILL.md",
            path / "LICENSE.txt",
            path / "agents" / "openai.yaml",
        ]
        for required in required_paths:
            if not required.exists():
                fail(errors, f"{path}: missing skill metadata file {required.relative_to(path)}")
        metadata_path = path / "agents" / "openai.yaml"
        if metadata_path.exists():
            metadata = load_yaml(metadata_path)
            interface = metadata.get("interface", {}) if isinstance(metadata, dict) else {}
            for key in ["display_name", "short_description", "default_prompt"]:
                if not interface.get(key):
                    fail(errors, f"{metadata_path}: missing interface.{key}")


def validate_workflows(errors: list[str]) -> None:
    tools_by_server, server_ids = mcp_tool_index()
    skills = skill_ids()
    for example_dir in sorted(path for path in (ROOT / "examples").iterdir() if path.is_dir()):
        if not (example_dir / "workflow.yaml").exists():
            fail(errors, f"{example_dir}: example is missing workflow.yaml")

    workflow_paths = sorted((ROOT / "examples").glob("*/workflow.yaml"))

    for path in workflow_paths:
        data = load_yaml(path)
        validate_json_schema(errors, data, "workflow.schema.json", path)
        for key in ["id", "title", "risk_default", "steps", "verification"]:
            if key not in data:
                fail(errors, f"{path}: missing required key {key}")

        required_servers = set(data.get("required_mcp_servers", []))
        optional_servers = set(data.get("optional_mcp_servers", []))
        workflow_servers = required_servers | optional_servers
        for server in workflow_servers:
            if server not in server_ids:
                fail(errors, f"{path}: unknown MCP server {server}")

        for skill in data.get("required_skills", []):
            if skill not in skills:
                fail(errors, f"{path}: unknown skill {skill}")

        available_tools: set[str] = set()
        for server in workflow_servers:
            available_tools |= tools_by_server.get(server, set())

        for step in data.get("steps", []):
            action = step.get("action")
            risk = step.get("risk")
            if not action:
                fail(errors, f"{path}: workflow step missing action")
            elif action not in available_tools:
                fail(errors, f"{path}: action {action} is not provided by workflow MCP servers")
            if risk in RISKS_REQUIRING_APPROVAL:
                fail(errors, f"{path}: step {action} uses risk={risk}; workflows should plan writes, not execute them")

        approvals = set(data.get("approval_required_for", []))
        known_tools = set().union(*tools_by_server.values()) if tools_by_server else set()
        for approval in approvals:
            if approval not in known_tools and approval not in GENERIC_APPROVAL_LABELS:
                fail(errors, f"{path}: approval_required_for references unknown action {approval}")


def validate_catalog(errors: list[str]) -> None:
    path = ROOT / "catalog" / "index.yaml"
    data = load_yaml(path)
    repository = data.get("repository", {})
    for key in ["org", "name", "slug", "url", "skills_install"]:
        if not repository.get(key):
            fail(errors, f"{path}: repository.{key} is required")
    if repository.get("slug") and repository.get("skills_install"):
        if repository["slug"] not in repository["skills_install"]:
            fail(errors, f"{path}: repository.skills_install should include repository.slug")
    for section in ["docs", "templates", "guardrails"]:
        for entry in data.get(section, []):
            target = ROOT / entry["path"]
            if not target.exists():
                fail(errors, f"{path}: {section} entry points at missing path {entry['path']}")
    for section in ["mcp_servers", "skills"]:
        for entry in data.get("entries", {}).get(section, []):
            target = ROOT / entry["path"]
            if not target.exists():
                fail(errors, f"{path}: {section} entry points at missing path {entry['path']}")
    for section in ["project"]:
        for entry in data.get("entries", {}).get(section, []):
            target = ROOT / entry["path"]
            if not target.exists():
                fail(errors, f"{path}: {section} entry points at missing path {entry['path']}")


def validate_release_docs(errors: list[str]) -> None:
    required_paths = [
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "CODE_OF_CONDUCT.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "SECURITY.md",
        ROOT / "LICENSE",
        ROOT / "docs" / "index.md",
    ]
    for path in required_paths:
        if not path.exists():
            fail(errors, f"missing release document {path}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    catalog = load_yaml(ROOT / "catalog" / "index.yaml")
    repository = catalog.get("repository", {})
    slug = repository.get("slug")
    install = repository.get("skills_install")
    if slug and slug not in readme:
        fail(errors, "README.md should include catalog repository.slug")
    if install and install not in readme:
        fail(errors, "README.md should include catalog repository.skills_install")
    required_readme_signals = [
        "What This Is",
        "What This Is Not",
        "Quick Start",
        "Safety Model",
        "Supported Domains",
        "Supported Clients",
        "Common Commands",
        "Documentation Map",
        "Current Status",
        "Contributing",
        "License",
    ]
    for signal in required_readme_signals:
        if signal not in readme:
            fail(errors, f"README.md missing release-facing section {signal}")


def validate_client_docs(errors: list[str]) -> None:
    required_docs = {
        "openclaw": ROOT / "docs" / "quickstart-openclaw.md",
        "hermes": ROOT / "docs" / "quickstart-hermes.md",
        "claude": ROOT / "docs" / "quickstart-claude.md",
        "codex": ROOT / "docs" / "quickstart-codex.md",
        "cursor": ROOT / "docs" / "quickstart-cursor.md",
        "grok": ROOT / "docs" / "quickstart-grok.md",
    }
    catalog = load_yaml(ROOT / "catalog" / "index.yaml")
    catalog_paths = {entry["path"] for entry in catalog.get("docs", [])}
    compatibility_path = ROOT / "docs" / "client-compatibility.md"
    if not compatibility_path.exists():
        fail(errors, f"missing required client compatibility doc {compatibility_path}")
    compatibility_text = compatibility_path.read_text(encoding="utf-8") if compatibility_path.exists() else ""

    for client, path in required_docs.items():
        if not path.exists():
            fail(errors, f"missing required {client} quickstart {path}")
            continue
        rel_path = str(path.relative_to(ROOT))
        if rel_path not in catalog_paths:
            fail(errors, f"{path}: quickstart is missing from catalog docs")
        text = path.read_text(encoding="utf-8").lower()
        if "read-only" not in text:
            fail(errors, f"{path}: quickstart must tell users to start read-only")
        if client not in compatibility_text.lower():
            fail(errors, f"{compatibility_path}: missing client {client}")


def validate_action_risk_matrix(errors: list[str]) -> None:
    path = ROOT / "guardrails" / "action-risk-matrix.yaml"
    if not path.exists():
        fail(errors, f"missing required action risk matrix {path}")
        return

    data = load_yaml(path)
    validate_json_schema(errors, data, "action-risk-matrix.schema.json", path)
    categories = data.get("categories", [])
    if not categories:
        fail(errors, f"{path}: categories are required")
        return

    required_ids = {
        "read",
        "plan",
        "write",
        "credential-access",
        "network-exposure",
        "storage-risk",
        "destructive",
        "unknown",
    }
    seen = {category.get("id") for category in categories}
    missing = required_ids - seen
    if missing:
        fail(errors, f"{path}: missing required categories {sorted(missing)}")

    allowed_decisions = {"allow_readonly", "approval_required", "destructive_approval_required", "unknown_requires_review"}
    for category in categories:
        category_id = category.get("id", "<missing>")
        decision = category.get("decision")
        requires_approval = category.get("requires_approval")
        if decision not in allowed_decisions:
            fail(errors, f"{path}: category {category_id} has unknown decision {decision}")
        if category_id in {"read", "plan"} and requires_approval is not False:
            fail(errors, f"{path}: category {category_id} should not require approval")
        if category_id not in {"read", "plan"} and requires_approval is not True:
            fail(errors, f"{path}: category {category_id} should require approval")
        for key in ["examples", "required_evidence"]:
            if not category.get(key):
                fail(errors, f"{path}: category {category_id} missing {key}")


def validate_inventory(errors: list[str]) -> None:
    paths = sorted((ROOT / "templates" / "inventory").glob("*.yaml"))
    for path in paths:
        data = load_yaml(path)
        validate_json_schema(errors, data, "inventory.schema.json", path)
        if "homelab" not in data or "nodes" not in data:
            fail(errors, f"{path}: inventory example must include homelab and nodes")
        if not data.get("homelab", {}).get("name"):
            fail(errors, f"{path}: inventory homelab.name is required")
        for section in ["nodes", "services", "storage", "agents"]:
            seen: set[str] = set()
            for item in data.get(section, []) or []:
                item_id = item.get("id")
                if not item_id:
                    fail(errors, f"{path}: {section} item missing id")
                    continue
                if item_id in seen:
                    fail(errors, f"{path}: duplicate id {item_id} in {section}")
                seen.add(item_id)

    json_path = ROOT / "templates" / "inventory" / "homelab.inventory.example.json"
    if json_path.exists():
        validate_json_schema(errors, load_json(json_path), "inventory.schema.json", json_path)


def validate_policies(errors: list[str]) -> None:
    for path in sorted((ROOT / "guardrails" / "policies").glob("*.yaml")):
        validate_json_schema(errors, load_yaml(path), "policy.schema.json", path)


def validate_playbooks(errors: list[str]) -> None:
    required_paths = [
        ROOT / "playbooks" / "ansible" / "README.md",
        ROOT / "playbooks" / "ansible" / "inventory.example.ini",
        ROOT / "playbooks" / "ansible" / "read-only-audit.yml",
    ]
    for path in required_paths:
        if not path.exists():
            fail(errors, f"missing required playbook asset {path}")

    playbook_path = ROOT / "playbooks" / "ansible" / "read-only-audit.yml"
    if not playbook_path.exists():
        return

    data = load_yaml(playbook_path)
    if not isinstance(data, list) or not data:
        fail(errors, f"{playbook_path}: expected a non-empty Ansible play list")
        return

    forbidden_tokens = [
        "ansible.builtin.apt",
        "ansible.builtin.copy",
        "ansible.builtin.file",
        "ansible.builtin.package",
        "ansible.builtin.reboot",
        "ansible.builtin.service",
        "ansible.builtin.systemd",
        "ansible.builtin.template",
        "ansible.builtin.user",
        "mkfs",
        "parted",
        "rm -rf",
        "shutdown",
        "state: absent",
        "state: latest",
        "state: present",
    ]
    lowered = playbook_path.read_text(encoding="utf-8").lower()
    for token in forbidden_tokens:
        if token.lower() in lowered:
            fail(errors, f"{playbook_path}: read-only audit contains forbidden token {token}")

    for play in data:
        if play.get("become") not in (False, None):
            fail(errors, f"{playbook_path}: read-only audit should not enable become")
        if not play.get("hosts"):
            fail(errors, f"{playbook_path}: play missing hosts")
        for task in play.get("tasks", []):
            if "ansible.builtin.command" in task and task.get("changed_when") is not False:
                name = task.get("name", "<unnamed>")
                fail(errors, f"{playbook_path}: command task {name} must set changed_when: false")


def validate_agent_runtime_templates(errors: list[str]) -> None:
    required_paths = [
        ROOT / "templates" / "agent-runtime" / "README.md",
        ROOT / "templates" / "agent-runtime" / "systemd" / "openclaw.service.example",
        ROOT / "templates" / "agent-runtime" / "systemd" / "hermes.service.example",
        ROOT / "templates" / "agent-runtime" / "launchd" / "com.agentic-homelab.agent.example.plist",
    ]
    for path in required_paths:
        if not path.exists():
            fail(errors, f"missing required agent runtime template {path}")

    for path in required_paths[1:3]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for required in ["User=<agent-user>", "EnvironmentFile=<protected-env-file>", "NoNewPrivileges=true"]:
            if required not in text:
                fail(errors, f"{path}: missing service hardening/example field {required}")


def validate_agent_instruction_template(errors: list[str]) -> None:
    template_path = ROOT / "templates" / "agent-instructions" / "AGENTS.md"
    readme_path = ROOT / "templates" / "agent-instructions" / "README.md"
    for path in [readme_path, template_path]:
        if not path.exists():
            fail(errors, f"missing required agent instruction template asset {path}")
            return

    text = template_path.read_text(encoding="utf-8")
    required_phrases = [
        "Observe read-only state first",
        "Requires explicit approval",
        "Forbidden unless the human gives a separate destructive-action approval",
        "Do not print, copy, store, or summarize secret values",
        "Do not execute the command or tool until the human approves that exact action",
        "Use at least one external verifier after a change",
    ]
    for phrase in required_phrases:
        if phrase not in text:
            fail(errors, f"{template_path}: missing required safety phrase {phrase!r}")


def scan_for_accidental_secrets(errors: list[str]) -> None:
    skipped_dirs = {".git", "node_modules", ".venv", "__pycache__"}
    skipped_files = {ROOT / "scripts" / "validate_repo.py"}
    for path in ROOT.rglob("*"):
        if any(part in skipped_dirs for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path in skipped_files:
            continue
        if path.suffix == ".py":
            continue
        if path.name == ".env.example":
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lowered = text.lower()
        for pattern in SECRET_PATTERNS:
            if pattern.lower() in lowered and "docs/agent-lessons-from-sessions.md" not in str(path):
                fail(errors, f"{path}: possible secret pattern found: {pattern}")


def validate_diagnostics_generator(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "bundle"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "create_diagnostics_bundle.py"),
                "--output",
                str(output),
                "--inventory",
                str(ROOT / "templates" / "inventory" / "homelab.inventory.example.yaml"),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            fail(errors, f"diagnostics generator failed: {proc.stderr.strip()}")
            return
        for required in ["manifest.json", "env-names.txt", "redactions.txt", "README.md"]:
            if not (output / required).exists():
                fail(errors, f"diagnostics generator did not create {required}")


def validate_guardrail_checker(errors: list[str]) -> None:
    checks = [
        (["list_nodes", "--format", "json"], "allow_readonly"),
        (["delete_guest", "--server", "proxmox", "--format", "json"], "destructive_approval_required"),
        (["rm -rf /tank/media", "--format", "json"], "destructive_approval_required"),
        (["network-exposure", "--format", "json"], "approval_required"),
        (["destructive", "--format", "json"], "destructive_approval_required"),
        (["totally_unknown_action", "--format", "json"], "unknown_requires_review"),
    ]
    for args, expected_decision in checks:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "guardrail_check.py"), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            fail(errors, f"guardrail checker returned non-json output for {args}: {proc.stdout}")
            continue
        if data.get("decision") != expected_decision:
            fail(errors, f"guardrail checker decision for {args} was {data.get('decision')}, expected {expected_decision}")
        if args[0] in {"network-exposure", "destructive"} and not data.get("required_evidence"):
            fail(errors, f"guardrail checker matrix result for {args} did not include required_evidence")


def validate_mcp_config_generator(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "mcp-config.json"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "generate_mcp_config.py"),
                "--inventory",
                str(ROOT / "templates" / "inventory" / "homelab.inventory.example.json"),
                "--output",
                str(output),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            fail(errors, f"MCP config generator failed: {proc.stderr.strip()}")
            return
        try:
            data = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(errors, f"MCP config generator produced invalid JSON: {exc}")
            return
        servers = data.get("mcpServers", {})
        if not servers:
            fail(errors, "MCP config generator produced no mcpServers")
        for name, config in servers.items():
            args = config.get("args", [])
            if not args:
                fail(errors, f"MCP config server {name} has no args")
                continue
            server_path = Path(args[0])
            if not server_path.exists():
                fail(errors, f"MCP config server {name} points at missing path {server_path}")


def validate_bootstrap_generator(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "starter"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "bootstrap_homelab_repo.py"), str(output)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            fail(errors, f"bootstrap generator failed: {proc.stderr.strip()}")
            return
        required_paths = [
            "README.md",
            "AGENTS.md",
            "homelab.inventory.yaml",
            "maintenance-log.md",
            "diagnostics/.gitkeep",
            "guardrails/policies/default-policy.yaml",
            "guardrails/action-risk-matrix.yaml",
        ]
        for required in required_paths:
            if not (output / required).exists():
                fail(errors, f"bootstrap generator did not create {required}")

        second_proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "bootstrap_homelab_repo.py"), str(output)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if second_proc.returncode != 0:
            fail(errors, f"bootstrap generator failed on existing directory: {second_proc.stderr.strip()}")
        if "skip existing" not in second_proc.stdout:
            fail(errors, "bootstrap generator should skip existing files without --force")


def validate_workflow_chooser(errors: list[str]) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "choose_workflow.py"),
            "--inventory",
            str(ROOT / "templates" / "inventory" / "homelab.inventory.example.yaml"),
            "--format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        fail(errors, f"workflow chooser failed: {proc.stderr.strip()}")
        return
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        fail(errors, f"workflow chooser returned non-json output: {proc.stdout}")
        return
    recommendations = data.get("recommendations", [])
    if not recommendations:
        fail(errors, "workflow chooser returned no recommendations")
        return
    for item in recommendations:
        path = ROOT / item.get("path", "")
        if not path.exists():
            fail(errors, f"workflow chooser recommended missing workflow {item.get('path')}")
        if not item.get("reason") or not item.get("safety_note"):
            fail(errors, f"workflow chooser recommendation missing reason or safety_note: {item}")


def validate_release_audit(errors: list[str]) -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "release_audit.py"), "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        try:
            report = json.loads(proc.stdout)
            failing = [i for i in report.get("items", []) if i.get("status") == "fail"]
            if failing:
                detail = "; ".join(f"{i.get('name')}: {i.get('evidence')}" for i in failing)
        except json.JSONDecodeError:
            pass
        fail(errors, f"release audit failed: {detail}")
        return
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        fail(errors, f"release audit returned non-json output: {proc.stdout}")
        return
    items = data.get("items", [])
    if not items:
        fail(errors, "release audit returned no items")
        return
    statuses = {item.get("status") for item in items}
    if "manual" not in statuses:
        fail(errors, "release audit must include manual real-environment checks")
    if data.get("failed") != 0:
        fail(errors, f"release audit reported failures: {data.get('failed')}")


def validate_doctor(errors: list[str]) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "doctor.py"),
            "--inventory",
            str(ROOT / "templates" / "inventory" / "homelab.inventory.example.json"),
            "--format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        fail(errors, f"doctor returned non-json output: {proc.stdout}")
        return
    checks = data.get("checks", [])
    if not checks:
        fail(errors, "doctor returned no checks")
    hard_failures = [item for item in checks if item.get("status") == "fail"]
    if hard_failures:
        fail(errors, f"doctor reported hard failures: {hard_failures}")


def main() -> int:
    errors: list[str] = []
    validate_catalog(errors)
    validate_release_docs(errors)
    validate_client_docs(errors)
    validate_action_risk_matrix(errors)
    validate_policies(errors)
    validate_mcp_manifests(errors)
    validate_skill_metadata(errors)
    validate_workflows(errors)
    validate_inventory(errors)
    validate_playbooks(errors)
    validate_agent_runtime_templates(errors)
    validate_agent_instruction_template(errors)
    scan_for_accidental_secrets(errors)
    validate_diagnostics_generator(errors)
    validate_guardrail_checker(errors)
    validate_mcp_config_generator(errors)
    validate_bootstrap_generator(errors)
    validate_workflow_chooser(errors)
    validate_release_audit(errors)
    validate_doctor(errors)

    if errors:
        print("agentic-homelab validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("agentic-homelab validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
