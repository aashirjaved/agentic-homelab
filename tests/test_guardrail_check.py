"""Behavioral tests locking the guardrail safety contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from guardrail_check import apply_policy, classify  # noqa: E402


class GuardrailDecisionTests(unittest.TestCase):
    def test_read_tool_is_allowed(self) -> None:
        result = classify("list_nodes", server="proxmox")
        self.assertEqual(result["decision"], "allow_readonly")
        self.assertEqual(result["risk"], "read")

    def test_destructive_tool_requires_destructive_approval(self) -> None:
        result = classify("delete_guest", server="proxmox")
        self.assertEqual(result["decision"], "destructive_approval_required")
        self.assertTrue(result["required_evidence"])

    def test_destructive_pattern_overrides_label(self) -> None:
        for command in (
            "rm -rf /tank/media",
            "rm -fr /tank/media",
            "rm  -r  -f /tank/media",
            "mkfs.ext4 /dev/sda",
            "zfs destroy tank/data",
            "dd if=/dev/zero of=/dev/sda",
            "shred /dev/sdb",
        ):
            result = classify(command)
            self.assertEqual(result["decision"], "destructive_approval_required", command)

    def test_benign_actions_not_false_positived(self) -> None:
        for action in ("list_nodes", "read_container_logs", "check_backup_freshness"):
            self.assertNotEqual(classify(action)["decision"], "destructive_approval_required", action)

    def test_unknown_action_fails_closed(self) -> None:
        result = classify("definitely-not-a-real-action")
        self.assertEqual(result["decision"], "unknown_requires_review")

    def test_matrix_categories_map_to_documented_decisions(self) -> None:
        self.assertEqual(classify("network-exposure")["decision"], "approval_required")
        self.assertEqual(classify("destructive")["decision"], "destructive_approval_required")

    def test_policy_is_loaded_and_never_relaxes(self) -> None:
        result = apply_policy(classify("list_nodes", server="proxmox"))
        self.assertEqual(result["policy"]["mode"], "read-only")
        self.assertEqual(result["decision"], "allow_readonly")

    def test_policy_escalates_credential_access(self) -> None:
        # A hypothetical allow_readonly result with a policy-gated risk must escalate.
        fabricated = {"decision": "allow_readonly", "risk": "credential-access", "next_step": ""}
        result = apply_policy(fabricated)
        self.assertEqual(result["decision"], "approval_required")
        self.assertTrue(result["requires_approval"])


class HookModeTests(unittest.TestCase):
    def run_hook(self, payload: object) -> dict:
        import json
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "guardrail_check.py"), "--hook"],
            input=payload if isinstance(payload, str) else json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)["hookSpecificOutput"]

    def test_read_tool_allowed(self) -> None:
        out = self.run_hook({"tool_name": "mcp__agentic-homelab-proxmox__list_nodes", "tool_input": {}})
        self.assertEqual(out["permissionDecision"], "allow")

    def test_destructive_tool_denied(self) -> None:
        out = self.run_hook({"tool_name": "mcp__agentic-homelab-proxmox__delete_guest", "tool_input": {}})
        self.assertEqual(out["permissionDecision"], "deny")

    def test_destructive_arguments_denied_despite_benign_tool_name(self) -> None:
        out = self.run_hook({
            "tool_name": "mcp__agentic-homelab-docker__read_container_logs",
            "tool_input": {"container": "app", "extra": "rm -rf /var/lib/docker"},
        })
        self.assertEqual(out["permissionDecision"], "deny")

    def test_malformed_stdin_fails_closed(self) -> None:
        out = self.run_hook('{"tool_name": broken')
        self.assertEqual(out["permissionDecision"], "deny")

    def test_missing_tool_name_fails_closed(self) -> None:
        out = self.run_hook({"tool_input": {}})
        self.assertEqual(out["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
