import argparse
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agentic_homelab import cli


def sample_report():
    return {
        "homelab": "test-lab",
        "observed_at": "2026-08-14T00:00:00Z",
        "read_only": True,
        "summary": {"nodes": 1, "services": 1, "storage": 0, "stacks": 0, "networks": 0,
                    "relationships": 0, "risks": 0, "unknowns": 0, "unresolved_relationships": 0},
        "findings": [], "unknowns": [], "relationships": [], "evidence": [],
        "timeline": {"status": "baseline", "events": [], "previous_observed_at": None},
        "recovery_readiness": {
            "principle": "Declared recovery evidence only.",
            "summary": {"proven": 0, "partial": 0, "unproven": 1, "unrecoverable": 0},
            "services": [{"service": "jellyfin", "status": "unproven", "score": 0,
                          "checks": [], "next_actions": ["Supply restore evidence."]}],
        },
        "update_intelligence": {"principle": "Supplied update evidence only.", "plans": []},
        "investigation": {
            "target": "jellyfin", "status": "investigated", "suggestions": [],
            "conclusion": "No likely cause is established.", "dependencies": [], "impacted": [],
            "hypotheses": [{"rank": 1, "confidence": "insufficient-evidence", "score": 0, "subject": "jellyfin",
                            "summary": "No current symptom explains the incident.", "supporting_evidence": [],
                            "impacted": [], "recommended_action": "Collect more evidence.",
                            "verification": ["Check service health."]}],
        },
    }


class CliTests(unittest.TestCase):
    def run_cli(self, argv):
        output = io.StringIO()
        with patch.object(cli, "build_report", return_value=sample_report()) as build, patch("sys.stdout", output):
            code = cli.main(argv)
        return code, output.getvalue(), build

    def test_investigate_is_a_real_section_specific_command(self):
        code, output, build = self.run_cli(["investigate", "jellyfin", "--no-discover"])
        self.assertEqual(code, 0)
        self.assertTrue(output.startswith("# Investigating jellyfin"))
        self.assertNotIn("# Recovery evidence", output)
        self.assertEqual(build.call_args.kwargs["investigate_target"], "jellyfin")

    def test_changes_and_recovery_render_only_the_requested_view(self):
        _, changes, _ = self.run_cli(["changes", "--no-history"])
        _, recovery, _ = self.run_cli(["recovery", "--no-discover"])
        self.assertTrue(changes.startswith("# What changed"))
        self.assertTrue(recovery.startswith("# Recovery evidence"))
        self.assertNotIn("# Homelab graph", changes + recovery)

    def test_updates_enables_update_collection_for_selected_service(self):
        _, output, build = self.run_cli(["updates", "jellyfin", "--format", "json"])
        self.assertEqual(json.loads(output)["principle"], "Supplied update evidence only.")
        self.assertTrue(build.call_args.kwargs["include_updates"])
        self.assertEqual(build.call_args.kwargs["update_target"], "jellyfin")

    def test_doctor_json_returns_the_complete_report(self):
        _, output, _ = self.run_cli(["doctor", "--format", "json"])
        self.assertEqual(json.loads(output)["homelab"], "test-lab")

    def test_share_creates_the_bundle_instead_of_aliasing_doctor(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle"
            stdout = io.StringIO()
            with patch.object(cli, "build_report", return_value=sample_report()), patch("sys.stdout", stdout):
                code = cli.main(["share", str(output), "--no-discover"])
            self.assertEqual(code, 0)
            self.assertEqual({path.name for path in output.iterdir()},
                             {"report.md", "report.json", "manifest.json", "README.md"})
            self.assertIn("Diagnostic bundle written", stdout.getvalue())

    def test_remote_ssh_options_are_structured_and_forwarded(self):
        _, _, build = self.run_cli([
            "doctor", "--no-local", "--ssh", "apps=root@apps.internal", "--ssh-identity", "/tmp/key",
            "--ssh-host-key-alias", "apps=apps.tailnet",
        ])
        self.assertFalse(build.call_args.kwargs["discover_local_host"])
        self.assertEqual(build.call_args.kwargs["ssh_targets"], {"apps": "root@apps.internal"})
        self.assertEqual(build.call_args.kwargs["ssh_identity"], Path("/tmp/key"))
        self.assertEqual(build.call_args.kwargs["ssh_host_key_aliases"], {"apps": "apps.tailnet"})

    def test_ssh_assignment_rejects_option_injection(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.assignment("apps=-oProxyCommand=bad")


if __name__ == "__main__":
    unittest.main()
