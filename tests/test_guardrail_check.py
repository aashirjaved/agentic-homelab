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
        for command in ("rm -rf /tank/media", "mkfs.ext4 /dev/sda", "zfs destroy tank/data"):
            result = classify(command)
            self.assertEqual(result["decision"], "destructive_approval_required", command)

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


if __name__ == "__main__":
    unittest.main()
