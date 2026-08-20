from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agentic_homelab import doctor

ROOT = Path(__file__).resolve().parents[1]


class HomelabDoctorTests(unittest.TestCase):
    def test_builds_graph_and_finds_recovery_and_shared_dependency_risks(self):
        inventory = {
            "homelab": {"name": "test-lab"},
            "nodes": [{"id": "docker-01", "role": "docker"}],
            "services": [
                {"id": "jellyfin", "kind": "media", "runs_on": "docker-01", "uses_storage": ["nas"]},
                {"id": "immich", "kind": "photos", "runs_on": "docker-01", "uses_storage": ["nas"]},
            ],
            "storage": [{"id": "nas", "kind": "nas", "mounted_by": ["docker-01"], "backup_status": "unknown"}],
        }
        report = doctor.inspect_inventory(inventory)
        codes = {finding["code"] for finding in report["findings"]}
        self.assertEqual(report["summary"]["relationships"], 5)
        self.assertIn("recovery-unproven", codes)
        self.assertIn("shared-dependency", codes)
        self.assertTrue(report["read_only"])

    def test_reports_missing_relationship_target(self):
        report = doctor.inspect_inventory({
            "homelab": {"name": "broken"},
            "nodes": [],
            "services": [{"id": "app", "kind": "web", "runs_on": "missing-host"}],
        })
        finding = next(item for item in report["findings"] if item["code"] == "missing-dependency")
        self.assertEqual(finding["subject"], "app")

    def test_share_report_redacts_private_addresses(self):
        report = doctor.inspect_inventory({"homelab": {"name": "lab at 192.168.1.20"}, "nodes": []})
        shared = doctor.redact(doctor.render_markdown(report, shared=True))
        self.assertNotIn("192.168.1.20", shared)
        self.assertIn("[redacted-private-address]", shared)
        self.assertIn("No changes have been made", shared)

    def test_share_report_redacts_home_directory_usernames(self):
        shared = doctor.redact("daemon unavailable at /Users/alice/.docker/run.sock and /home/bob/data")
        self.assertNotIn("alice", shared)
        self.assertNotIn("bob", shared)
        self.assertIn("/Users/[redacted-user]/", shared)

    def test_loads_yaml_and_json(self):
        with tempfile.TemporaryDirectory() as directory:
            yaml_path = Path(directory) / "lab.yaml"
            json_path = Path(directory) / "lab.json"
            yaml_path.write_text("homelab:\n  name: yaml-lab\nnodes: []\n", encoding="utf-8")
            json_path.write_text('{"homelab":{"name":"json-lab"},"nodes":[]}', encoding="utf-8")
            self.assertEqual(doctor.load_inventory(yaml_path)["homelab"]["name"], "yaml-lab")
            self.assertEqual(doctor.load_inventory(json_path)["homelab"]["name"], "json-lab")

    def test_normalizes_keyed_operator_inventory_without_a_duplicate_flat_file(self):
        inventory = doctor.normalize_inventory({"nodes": {
            "pve": {"role": "proxmox", "lan_ip": "192.0.2.1", "storage_pool": "tank",
                    "capabilities": ["proxmox", "zfs"]},
            "apps": {"role": "docker", "parent": "pve", "proxmox_ctid": 200,
                     "services": {"immich": "http://192.0.2.2:2283",
                                  "immich_public": "https://photos.example"},
                     "stacks": {"immich": "/srv/stacks/immich"}},
            "media": {"role": "docker", "mounts": {"movies": "/mnt/pve/movies"},
                      "services": {"jellyfin": "http://192.0.2.3:8096"}},
        }}, Path("repo/infra/inventory.yaml"))
        self.assertEqual(inventory["homelab"]["name"], "repo")
        self.assertEqual({node["id"] for node in inventory["nodes"]}, {"pve", "media"})
        apps = next(service for service in inventory["services"] if service["id"] == "apps")
        immich = next(service for service in inventory["services"] if service.get("name") == "immich")
        self.assertEqual(apps["runs_on"], "pve")
        self.assertEqual(immich["runs_on"], "apps")
        self.assertEqual(immich["endpoint_count"], 2)
        self.assertEqual(immich["member_of"], "compose-stack:apps/immich")
        mount = next(store for store in inventory["storage"] if store["id"] == "mount:media:movies")
        self.assertEqual(mount["server_host"], "pve")

    def test_keyed_inventory_preserves_canonical_recovery_overlays(self):
        inventory = doctor.normalize_inventory({
            "nodes": {"apps": {"role": "docker", "services": {"immich": "http://192.0.2.1:2283"}}},
            "services": [{"id": "immich", "kind": "photos", "recovery": {
                "configuration_status": "version-controlled",
            }}],
            "storage": [{"id": "photos", "kind": "zfs-dataset", "backup_status": "fresh"}],
            "restore_tests": [{"service": "immich", "status": "unknown"}],
        })
        immich = next(service for service in inventory["services"] if service["id"] == "immich")
        self.assertEqual(immich["recovery"]["configuration_status"], "version-controlled")
        self.assertEqual(inventory["storage"][0]["id"], "photos")
        self.assertEqual(inventory["restore_tests"][0]["service"], "immich")

    def test_keyed_inventory_skips_planning_prose_as_a_storage_pool(self):
        inventory = doctor.normalize_inventory({"nodes": {
            "future-backup": {
                "capabilities": ["zfs"],
                "storage_pool": "TBD — choose a mirrored pool after purchase",
            },
        }})
        self.assertEqual(inventory["storage"], [])

    def test_keyed_inventory_recognizes_outbound_and_loopback_services(self):
        inventory = doctor.normalize_inventory({"nodes": {
            "host": {"services": {
                "agent": "outbound websocket to http://monitor.internal:8090",
                "tts": "sidecar on 127.0.0.1:8000",
            }},
        }})
        services = {service["id"]: service for service in inventory["services"]}
        self.assertEqual(services["agent"]["exposure"], "outbound-only")
        self.assertEqual(services["tts"]["exposure"], "host-only")

    def test_tailscale_cgnat_address_is_not_public_exposure(self):
        self.assertEqual(doctor.endpoint_exposure(["http://100.67.243.101:8096"]), "private-lan")
        self.assertEqual(doctor.endpoint_exposure(["https://service.example"]), "public")

    def test_reconciles_declared_service_with_unique_live_compose_service(self):
        inventory = doctor.infer_topology({
            "nodes": [{"id": "apps"}],
            "services": [
                {"id": "postgres", "name": "postgres", "kind": "declared-service",
                 "runs_on": "apps", "source": "declared-keyed-inventory"},
                {"id": "apps/compute-postgres-1", "kind": "docker-container", "runs_on": "apps",
                 "compose_service": "postgres", "state": "running", "health": "healthy",
                 "exposure": "local-or-unpublished", "source": "docker"},
                {"id": "apps/api", "kind": "docker-container", "runs_on": "apps",
                 "depends_on": ["apps/compute-postgres-1"], "source": "docker"},
            ],
        })
        services = {service["id"]: service for service in inventory["services"]}
        self.assertNotIn("apps/compute-postgres-1", services)
        self.assertEqual(services["postgres"]["state"], "running")
        self.assertEqual(services["postgres"]["kind"], "docker-container")
        self.assertEqual(services["apps/api"]["depends_on"], ["postgres"])

    def test_reconciles_declared_mount_through_nfs_to_backing_filesystem(self):
        inventory = doctor.infer_topology({
            "nodes": [{"id": "media"}, {"id": "nas"}],
            "services": [{"id": "jellyfin", "runs_on": "media",
                          "uses_storage": ["remote-storage:nas:media"]}],
            "storage": [
                {"id": "mount:media:media", "kind": "network-mount", "mounted_by": ["media"],
                 "mount_target": "/mnt/nas/media", "source": "declared-keyed-inventory"},
                {"id": "remote-storage:nas:media", "kind": "nfs", "mounted_by": ["media"],
                 "mount_target": "/mnt/nas/media", "server_host": "nas", "export_path": "/tank/media",
                 "source": "host-storage"},
                {"id": "nas/tank", "kind": "local-filesystem", "mounted_by": ["nas"],
                 "mount_target": "/tank", "source": "host-storage"},
            ],
        })
        storage = {item["id"]: item for item in inventory["storage"]}
        jellyfin = next(item for item in inventory["services"] if item["id"] == "jellyfin")
        self.assertNotIn("remote-storage:nas:media", storage)
        self.assertEqual(jellyfin["uses_storage"], ["mount:media:media"])
        self.assertEqual(storage["mount:media:media"]["served_by"], "nas")
        self.assertEqual(storage["mount:media:media"]["backed_by"], "nas/tank")

    def test_proxmox_operational_storage_is_not_a_recovery_claim(self):
        inventory = {
            "nodes": [{"id": "pve"}],
            "storage": [{"id": "pve-storage:pve:local", "mounted_by": ["pve"],
                         "backup_status": "unknown", "source": "proxmox"}],
        }
        report = doctor.inspect_inventory(inventory, [])
        self.assertNotIn("recovery-unproven", {finding["code"] for finding in report["findings"]})

    def test_undeclared_stopped_container_is_stale_not_an_active_outage(self):
        inventory = {"nodes": [{"id": "host"}], "services": [
            {"id": "old", "kind": "docker-container", "runs_on": "host",
             "state": "exited", "source": "docker", "exposure": "local-or-unpublished"},
        ]}
        report = doctor.inspect_inventory(inventory, [])
        codes = {finding["code"] for finding in report["findings"]}
        self.assertIn("stale-container", codes)
        self.assertNotIn("service-not-running", codes)

    @patch.object(doctor, "discover_local")
    def test_remote_only_report_does_not_inspect_the_controller(self, discover_local):
        report = doctor.build_report(
            discover_local_host=False, discover_remote=False, use_history=False,
        )
        discover_local.assert_not_called()
        self.assertEqual(report["summary"]["nodes"], 0)

    def test_remote_collection_skips_docker_when_host_has_no_docker_capability(self):
        storage_evidence = {"source": "host-storage", "status": "ok", "detail": "observed storage"}
        with patch.object(doctor, "ssh_runner", return_value=object()), \
             patch.object(doctor, "host_storage_discovery", return_value=({}, storage_evidence)), \
             patch.object(doctor, "docker_discovery") as docker_discovery:
            _, evidence = doctor.collect_remote_host(
                "storage", "root@storage", {"role": "storage", "capabilities": ["zfs"]}, None, None,
            )
        docker_discovery.assert_not_called()
        self.assertEqual([item["source"] for item in evidence], ["ssh:storage:storage"])

    @patch.object(doctor.shutil, "which", return_value="/usr/bin/docker")
    def test_discovers_docker_services_mounts_and_health(self, _which):
        ps = (
            '{"ID":"abc","Names":"jellyfin","Image":"jellyfin:latest",'
            '"Status":"Up 2 hours","Ports":"0.0.0.0:8096->8096/tcp"}\n'
        )
        inspected = """[{
          "Name": "/jellyfin",
          "State": {"Status": "running", "Health": {"Status": "unhealthy"}},
          "Mounts": [{"Type": "bind", "Source": "/srv/media", "Destination": "/media"}]
        }]"""

        def runner(command, timeout=10):
            if command[1] == "ps":
                return 0, ps, ""
            return 0, inspected, ""

        inventory, evidence = doctor.docker_discovery(runner)
        report = doctor.inspect_inventory(inventory, [evidence])
        service = inventory["services"][0]
        codes = {finding["code"] for finding in report["findings"]}
        self.assertEqual(service["uses_storage"], [])
        self.assertEqual(service["bind_sources"], ["/srv/media"])
        self.assertIn("service-unhealthy", codes)
        self.assertIn("broad-listen", codes)
        self.assertEqual(evidence["status"], "ok")

    @patch.object(doctor.shutil, "which", return_value=None)
    def test_unavailable_discovery_is_explicit(self, _which):
        inventory, evidence = doctor.docker_discovery()
        self.assertEqual(inventory, {})
        self.assertEqual(evidence["status"], "unavailable")

    @patch.object(doctor.shutil, "which", return_value=None)
    def test_local_discovery_keeps_host_and_turns_missing_source_into_finding(self, _which):
        inventory, evidence = doctor.discover_local()
        report = doctor.inspect_inventory(inventory, evidence)
        self.assertEqual(report["summary"]["nodes"], 1)
        self.assertIn("evidence-gap", {finding["code"] for finding in report["findings"]})

    def test_declared_inventory_overrides_discovered_fields(self):
        merged = doctor.merge_inventory(
            {"homelab": {"name": "mine"}, "services": [{"id": "app", "kind": "declared"}]},
            {"services": [{"id": "app", "kind": "docker-container", "state": "running"}]},
        )
        self.assertEqual(merged["services"], [{"id": "app", "kind": "declared", "state": "running"}])

    def test_timeline_records_baseline_then_semantic_changes(self):
        before = doctor.make_snapshot({
            "nodes": [{"id": "host", "role": "docker"}],
            "services": [{"id": "app", "kind": "docker-container", "image": "app:1", "state": "running"}],
        }, "2026-01-01T00:00:00Z")
        after = doctor.make_snapshot({
            "nodes": [{"id": "host", "role": "docker"}],
            "services": [
                {"id": "app", "kind": "docker-container", "image": "app:2", "state": "exited"},
                {"id": "db", "kind": "docker-container", "state": "running"},
            ],
        }, "2026-01-02T00:00:00Z")
        baseline = doctor.build_timeline({"snapshots": []}, before)
        timeline = doctor.build_timeline({"snapshots": [before]}, after)
        self.assertEqual(baseline["status"], "baseline")
        self.assertEqual(timeline["status"], "tracked")
        changes = {(event["subject"], event["change"]) for event in timeline["events"]}
        self.assertIn(("app", "image"), changes)
        self.assertIn(("app", "state"), changes)
        self.assertIn(("db", "added"), changes)
        exited = next(event for event in timeline["events"] if event["change"] == "state")
        self.assertEqual(exited["severity"], "high")

    def test_timeline_reports_no_changes(self):
        snapshot = doctor.make_snapshot({"nodes": [{"id": "host", "role": "docker"}]}, "2026-01-01T00:00:00Z")
        current = {**snapshot, "observed_at": "2026-01-02T00:00:00Z"}
        timeline = doctor.build_timeline({"snapshots": [snapshot]}, current)
        self.assertEqual(timeline["events"], [])

    def test_history_is_bounded_and_snapshot_excludes_credentials(self):
        snapshot = doctor.make_snapshot({
            "nodes": [{"id": "host", "role": "proxmox", "address": "192.168.1.2",
                       "access": {"credential_ref": "secret-token"}}],
        }, "2026-01-01T00:00:00Z")
        serialized = str(snapshot)
        self.assertNotIn("secret-token", serialized)
        self.assertNotIn("192.168.1.2", serialized)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            history = {"snapshots": [{**snapshot, "observed_at": str(index)} for index in range(5)]}
            doctor.save_history(path, history, snapshot, limit=3)
            self.assertEqual(len(doctor.load_history(path)["snapshots"]), 3)

    def test_attach_timeline_replaces_change_history_unknown(self):
        report = doctor.inspect_inventory({"homelab": {"name": "lab"}, "nodes": []})
        doctor.attach_timeline(report, {"status": "baseline", "events": [], "previous_observed_at": None,
                                        "snapshot_count": 1, "history_error": None})
        self.assertNotIn(doctor.CHANGE_HISTORY_UNKNOWN, report["unknowns"])
        self.assertTrue(any("baseline" in unknown.lower() for unknown in report["unknowns"]))

    def incident_fixture(self):
        inventory = {
            "homelab": {"name": "incident-lab"},
            "nodes": [{"id": "docker", "role": "docker"}],
            "services": [
                {"id": "jellyfin", "kind": "media", "runs_on": "docker", "depends_on": ["dns"]},
                {"id": "dns", "kind": "dns", "runs_on": "docker", "state": "exited"},
            ],
        }
        return inventory, doctor.inspect_inventory(inventory)

    def test_investigator_ranks_failed_dependency_and_blast_radius(self):
        inventory, report = self.incident_fixture()
        result = doctor.investigate(report, inventory, "JELLYFIN")
        top = result["hypotheses"][0]
        self.assertEqual(result["target"], "jellyfin")
        self.assertEqual(top["subject"], "dns")
        self.assertEqual(top["code"], "service-not-running")
        self.assertEqual(top["confidence"], "likely")
        self.assertIn("jellyfin", top["impacted"])

    def test_investigator_uses_relevant_current_timeline_change(self):
        inventory = {"homelab": {"name": "lab"}, "nodes": [{"id": "host", "role": "docker"}],
                     "services": [{"id": "app", "kind": "web", "runs_on": "host"}]}
        report = doctor.inspect_inventory(inventory)
        report["timeline"] = {"events": [{"at": report["observed_at"], "severity": "medium", "category": "services",
                                            "subject": "app", "change": "image", "before": "app:1", "after": "app:2"}]}
        result = doctor.investigate(report, inventory, "app")
        self.assertEqual(result["hypotheses"][0]["code"], "recent-change")
        self.assertEqual(result["hypotheses"][0]["score"], 72)

    def test_investigator_handles_unknown_target_with_suggestion(self):
        inventory, report = self.incident_fixture()
        result = doctor.investigate(report, inventory, "jellyfinx")
        self.assertEqual(result["status"], "target-not-found")
        self.assertIn("jellyfin", result["suggestions"])

    def test_investigator_does_not_invent_cause_without_evidence(self):
        inventory = {"homelab": {"name": "lab"}, "services": [{"id": "healthy", "kind": "web"}]}
        report = doctor.inspect_inventory(inventory)
        result = doctor.investigate(report, inventory, "healthy")
        self.assertEqual(result["hypotheses"][0]["confidence"], "insufficient-evidence")
        self.assertEqual(result["hypotheses"][0]["score"], 0)

    def test_investigator_does_not_traverse_unrelated_host_mounts(self):
        inventory = {
            "nodes": [{"id": "host"}],
            "services": [{"id": "app", "runs_on": "host", "uses_storage": ["app-data"]}],
            "storage": [
                {"id": "app-data", "mounted_by": ["host"]},
                {"id": "unrelated", "mounted_by": ["host"]},
            ],
        }
        result = doctor.investigate(doctor.inspect_inventory(inventory), inventory, "app")
        self.assertIn("app-data", result["dependencies"])
        self.assertNotIn("unrelated", result["dependencies"])

    def test_investigator_leads_with_observed_healthy_state(self):
        inventory = {"services": [{"id": "app", "state": "running", "health": "reachable"}]}
        result = doctor.investigate(doctor.inspect_inventory(inventory), inventory, "app")
        self.assertEqual(result["current_observation"], {"state": "running", "health": "reachable"})
        self.assertIn("No current incident is established", result["conclusion"])

    def test_investigator_ranks_inactive_storage_as_likely_root_cause(self):
        inventory = {
            "nodes": [{"id": "host"}],
            "services": [{"id": "jellyfin", "runs_on": "host", "uses_storage": ["media"]}],
            "storage": [{"id": "media", "state": "inactive", "mounted_by": ["host"]}],
        }
        report = doctor.inspect_inventory(inventory)
        result = doctor.investigate(report, inventory, "jellyfin")
        self.assertEqual(result["hypotheses"][0]["code"], "storage-inactive")
        self.assertEqual(result["hypotheses"][0]["confidence"], "likely")

    def test_recovery_readiness_proven_for_complete_stateless_service(self):
        inventory = {"services": [{"id": "proxy", "kind": "proxy", "recovery": {
            "configuration_status": "version-controlled", "secrets_required": False,
            "data_required": False, "restore_runbook": "docs/restore-proxy.md",
            "last_restore_test": "2099-01-01T00:00:00Z",
        }}]}
        readiness = doctor.service_recovery_readiness(inventory["services"][0], inventory, [])
        self.assertEqual(readiness["status"], "proven")
        self.assertEqual(readiness["score"], 100)

    def test_recovery_readiness_partial_with_unverified_restore(self):
        inventory = {"services": [{"id": "app", "kind": "web", "uses_storage": ["data"], "recovery": {
            "configuration_status": "version-controlled", "secrets_status": "escrowed",
            "restore_runbook": "docs/restore-app.md", "last_restore_test": "never",
        }}], "storage": [{"id": "data", "kind": "volume", "backup_status": "fresh",
                           "failure_domain": "host", "backup_failure_domain": "nas"}]}
        edges = [doctor.asdict(edge) for edge in doctor.build_edges(inventory)]
        readiness = doctor.service_recovery_readiness(inventory["services"][0], inventory, edges)
        self.assertEqual(readiness["status"], "partial")
        self.assertIn("restore-test", readiness["missing_evidence"])

    def test_top_level_restore_test_is_consumed_and_not_reported_missing(self):
        inventory = {
            "services": [{"id": "app", "kind": "web", "recovery": {
                "configuration_status": "verified", "secrets_required": False, "data_required": False,
                "restore_runbook": "docs/restore-app.md",
            }}],
            "restore_tests": [{"service": "app", "status": "passed", "tested_at": "2099-01-01T00:00:00Z"}],
        }
        report = doctor.inspect_inventory(inventory)
        readiness = doctor.service_recovery_readiness(inventory["services"][0], inventory, [])
        self.assertEqual(readiness["status"], "proven")
        self.assertNotIn("No restore-test evidence is recorded.", report["unknowns"])

    def test_recovery_readiness_unrecoverable_when_data_or_key_is_missing(self):
        inventory = {"services": [{"id": "vault", "kind": "database", "uses_storage": ["data"], "recovery": {
            "configuration_status": "verified", "secrets_status": "lost", "restore_runbook": "restore.md",
            "last_restore_test": "never",
        }}], "storage": [{"id": "data", "kind": "volume", "backup_status": "missing",
                           "independent_backup": False}]}
        edges = [doctor.asdict(edge) for edge in doctor.build_edges(inventory)]
        readiness = doctor.service_recovery_readiness(inventory["services"][0], inventory, edges)
        self.assertEqual(readiness["status"], "unrecoverable")
        self.assertIn("secrets-and-keys", readiness["missing_evidence"])
        self.assertIn("data-backup", readiness["missing_evidence"])

    def test_attach_recovery_adds_service_level_finding(self):
        inventory = {"homelab": {"name": "lab"}, "services": [{"id": "app", "kind": "web", "recovery_required": True}]}
        report = doctor.inspect_inventory(inventory)
        doctor.attach_recovery_readiness(report, inventory)
        self.assertEqual(report["recovery_readiness"]["summary"]["unproven"], 1)
        self.assertIn("service-recovery-unproven", {finding["code"] for finding in report["findings"]})

    def test_recovery_scoring_does_not_mark_discovered_endpoints_as_failed(self):
        inventory = {"services": [
            {"id": "homepage", "kind": "dashboard", "recovery": {"data_required": False}},
            {"id": "dockerproxy", "kind": "declared-service"},
        ]}
        report = doctor.inspect_inventory(inventory)
        doctor.attach_recovery_readiness(report, inventory, include_findings=False)
        self.assertEqual([item["service"] for item in report["recovery_readiness"]["services"]], ["homepage"])
        self.assertEqual(report["recovery_readiness"]["coverage"]["unmodeled"], 1)

    def test_unknown_failure_domain_never_counts_as_separated(self):
        inventory = {"services": [{"id": "app", "kind": "web", "uses_storage": ["data"], "recovery": {
            "configuration_status": "verified", "secrets_required": False, "restore_runbook": "restore.md",
            "last_restore_test": "2099-01-01T00:00:00Z",
        }}], "storage": [{"id": "data", "kind": "volume", "backup_status": "fresh",
                           "failure_domain": "host", "backup_failure_domain": "unknown"}]}
        edges = [doctor.asdict(edge) for edge in doctor.build_edges(inventory)]
        readiness = doctor.service_recovery_readiness(inventory["services"][0], inventory, edges)
        domain = next(check for check in readiness["checks"] if check["name"] == "failure-domain-separation")
        self.assertEqual(domain["state"], "unknown")

    def update_fixture(self, recovery_status="proven", **update):
        service = {"id": "app", "kind": "web", "state": "running", "health": "healthy", "update": {
            "available": True, "current_version": "1", "target_version": "2",
            "release_notes_reviewed": True, "breaking_changes_reviewed": True,
            "rollback": "pin version 1", "verification": ["endpoint returns 200"], **update,
        }}
        inventory = {"services": [service]}
        report = doctor.inspect_inventory(inventory)
        report["timeline"] = {"events": []}
        recovery = {"service": "app", "status": recovery_status, "score": 100 if recovery_status == "proven" else 0}
        return service, report, recovery

    def test_update_plan_ready_only_when_all_gates_pass(self):
        service, report, recovery = self.update_fixture()
        plan = doctor.plan_service_update(service, report, recovery)
        self.assertEqual(plan["decision"], "ready-for-approval")
        self.assertIn("Approval is still required", plan["reason"])

    def test_update_plan_blocked_by_unhealthy_service(self):
        service, report, recovery = self.update_fixture()
        service["health"] = "unhealthy"
        plan = doctor.plan_service_update(service, report, recovery)
        self.assertEqual(plan["decision"], "blocked")
        self.assertEqual(next(g for g in plan["gates"] if g["name"] == "current-health")["state"], "fail")

    def test_update_plan_blocked_when_release_notes_explicitly_unreviewed(self):
        service, report, recovery = self.update_fixture(release_notes_reviewed=False)
        self.assertEqual(doctor.plan_service_update(service, report, recovery)["decision"], "blocked")

    def test_update_plan_caution_for_unknown_recovery_or_recent_change(self):
        service, report, recovery = self.update_fixture(recovery_status="unproven")
        report["timeline"] = {"events": [{"subject": "app", "at": report["observed_at"]}]}
        self.assertEqual(doctor.plan_service_update(service, report, recovery)["decision"], "caution")

    def test_update_intelligence_orders_ready_low_blast_radius_first(self):
        first, report, recovery = self.update_fixture()
        second = {**first, "id": "dependency"}
        inventory = {"services": [first, second, {"id": "consumer", "kind": "web", "depends_on": ["dependency"]}]}
        report = doctor.inspect_inventory(inventory)
        report["timeline"] = {"events": []}
        report["recovery_readiness"] = {"services": [recovery, {**recovery, "service": "dependency"},
                                                               {**recovery, "service": "consumer"}]}
        doctor.attach_update_intelligence(report, inventory)
        self.assertEqual(report["update_intelligence"]["plans"][0]["service"], "app")

    def test_proxmox_discovery_normalizes_nodes_guests_storage_and_tasks(self):
        responses = {
            "/nodes": [{"node": "pve-01", "status": "online"}],
            "/cluster/resources?type=vm": [{"node": "pve-01", "type": "qemu", "vmid": 101,
                                             "name": "docker-vm", "status": "running"}],
            "/cluster/tasks?limit=50": [{"node": "pve-01", "id": 101, "type": "qmstart", "status": "OK", "endtime": 100}],
            "/nodes/pve-01/storage": [{"storage": "local-zfs", "type": "zfspool", "active": 1}],
            "/nodes/pve-01/qemu/101/config": {"scsi0": "local-zfs:vm-101-disk-0,size=32G"},
        }
        def getter(path):
            return {"data": responses[path]}
        env = {"PROXMOX_API_URL": "https://pve.example", "PROXMOX_API_TOKEN_ID": "id",
               "PROXMOX_API_TOKEN_SECRET": "secret"}
        with patch.dict(doctor.os.environ, env, clear=False):
            inventory, evidence = doctor.proxmox_discovery(getter)
        self.assertEqual(evidence["status"], "ok")
        self.assertEqual(inventory["services"][0]["runs_on"], "pve-01")
        self.assertEqual(inventory["services"][0]["uses_storage"], ["pve-storage:pve-01:local-zfs"])
        self.assertEqual(inventory["storage"][0]["mounted_by"], ["pve-01"])
        self.assertEqual(inventory["changes"][0]["type"], "qmstart")
        self.assertEqual(inventory["changes"][0]["subject"], "docker-vm")

    def test_proxmox_not_configured_is_explicit_but_not_a_failure(self):
        with patch.dict(doctor.os.environ, {}, clear=True):
            inventory, evidence = doctor.proxmox_discovery()
        self.assertEqual(inventory, {})
        self.assertEqual(evidence["status"], "not-configured")

    def test_proxmox_keeps_inventory_when_guest_config_is_unavailable(self):
        responses = {
            "/nodes": [{"node": "pve-01", "status": "online"}],
            "/cluster/resources?type=vm": [{"node": "pve-01", "type": "qemu", "vmid": 101,
                                             "name": "docker-vm", "status": "running"}],
            "/cluster/tasks?limit=50": [],
            "/nodes/pve-01/storage": [],
        }
        def getter(path):
            if path.endswith("/config"):
                raise OSError("permission denied")
            return {"data": responses[path]}
        env = {"PROXMOX_API_URL": "https://pve.example", "PROXMOX_API_TOKEN_ID": "id",
               "PROXMOX_API_TOKEN_SECRET": "secret"}
        with patch.dict(doctor.os.environ, env, clear=False):
            inventory, evidence = doctor.proxmox_discovery(getter)
        self.assertEqual(evidence["status"], "partial")
        self.assertEqual(inventory["services"][0]["id"], "docker-vm")

    def test_remote_pvesh_discovery_does_not_require_api_environment(self):
        responses = {
            "/nodes": [{"node": "pve", "status": "online"}],
            "/cluster/resources?type=vm": [],
            "/cluster/tasks?limit=50": [],
            "/nodes/pve/storage": [],
        }
        with patch.dict(doctor.os.environ, {}, clear=True):
            inventory, evidence = doctor.proxmox_discovery(
                lambda path: {"data": responses[path]}, require_env=False,
            )
        self.assertEqual(evidence["status"], "ok")
        self.assertEqual(inventory["nodes"][0]["id"], "pve")

    def test_namespaces_remote_docker_topology_per_host(self):
        inventory = {
            "services": [{"id": "web", "runs_on": "local-host", "depends_on": ["db"],
                          "uses_storage": ["docker-volume:data"], "member_of": "compose-stack:app",
                          "network_segments": ["docker-network:default"]},
                         {"id": "db", "runs_on": "local-host"}],
            "storage": [{"id": "docker-volume:data", "mounted_by": ["local-host"]}],
            "stacks": [{"id": "compose-stack:app", "runs_on": "local-host"}],
            "network_segments": [{"id": "docker-network:default"}],
        }
        namespaced = doctor.namespace_remote_inventory(inventory, "apps")
        web = next(item for item in namespaced["services"] if item["id"] == "apps/web")
        self.assertEqual(web["depends_on"], ["apps/db"])
        self.assertEqual(web["uses_storage"], ["apps/docker-volume:data"])
        self.assertEqual(web["member_of"], "apps/compose-stack:app")
        self.assertEqual(web["network_segments"], ["apps/docker-network:default"])
        self.assertEqual(namespaced["storage"][0]["mounted_by"], ["apps"])

    def test_namespaces_remote_mount_before_cross_host_canonicalization(self):
        inventory = {"storage": [{"id": "remote-storage:nas:media", "mounted_by": ["local-host"]}]}
        namespaced = doctor.namespace_remote_inventory(inventory, "media")
        self.assertEqual(namespaced["storage"][0]["id"], "media/remote-storage:nas:media")

    def test_host_storage_parses_modern_linux_mount_output(self):
        def runner(command, timeout=10):
            if command[0] == "df":
                return 0, ("Filesystem 1024-blocks Used Available Capacity Mounted on\n"
                           "nas:/tank/media 100 50 50 50% /mnt/media\n"), ""
            return 0, "nas:/tank/media on /mnt/media type nfs4 (rw,relatime)\n", ""
        inventory, evidence = doctor.host_storage_discovery(runner)
        self.assertEqual(evidence["status"], "ok")
        self.assertEqual(inventory["storage"][0]["kind"], "nfs4")

    def test_remote_pvesh_getter_drops_api_only_limit_parameter(self):
        commands = []
        def runner(command, timeout=10):
            commands.append(command)
            return 0, "[]", ""
        getter = doctor.remote_pvesh_getter(runner)
        self.assertEqual(getter("/cluster/tasks?limit=50"), {"data": []})
        self.assertNotIn("--limit", commands[0])

    def test_host_storage_discovery_uses_private_opaque_ids(self):
        output = "Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/disk1 100 95 5 95% /Users/private\n"
        inventory, evidence = doctor.host_storage_discovery(lambda command: (0, output, ""))
        self.assertEqual(evidence["status"], "ok")
        self.assertTrue(inventory["storage"][0]["id"].startswith("local-filesystem:"))
        self.assertEqual(inventory["storage"][0]["mount_target"], "/Users/private")
        report = doctor.inspect_inventory(inventory)
        self.assertIn("storage-capacity-critical", {finding["code"] for finding in report["findings"]})
        self.assertNotIn("recovery-unproven", {finding["code"] for finding in report["findings"]})

    def test_external_tasks_join_unified_timeline(self):
        report = doctor.inspect_inventory({"homelab": {"name": "lab"}, "nodes": []})
        doctor.attach_external_changes(report, [{"source": "proxmox", "subject": "101", "type": "qmstop",
                                                  "status": "ERROR", "timestamp": 100}])
        event = report["timeline"]["events"][0]
        self.assertEqual(event["category"], "proxmox")
        self.assertEqual(event["severity"], "high")

    def test_recent_proxmox_task_correlates_with_guest_incident(self):
        inventory = {"nodes": [{"id": "pve", "role": "proxmox"}],
                     "services": [{"id": "docker-vm", "kind": "proxmox-qemu", "runs_on": "pve"}]}
        report = doctor.inspect_inventory(inventory)
        observed = doctor.datetime.fromisoformat(report["observed_at"].replace("Z", "+00:00"))
        recent = (observed - doctor.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        report["timeline"] = {"events": [{"at": recent, "severity": "info", "category": "proxmox",
                                            "subject": "docker-vm", "change": "qmreboot", "before": None,
                                            "after": "OK"}]}
        result = doctor.investigate(report, inventory, "docker-vm")
        self.assertEqual(result["hypotheses"][0]["code"], "recent-change")

    def test_endpoint_discovery_enriches_service_and_nas_without_retaining_url(self):
        inventory = {
            "services": [{"id": "jellyfin", "kind": "media", "healthcheck": {
                "url": "https://user-visible.example/health", "expected_status": 204}}],
            "storage": [{"id": "nas", "kind": "nas", "healthcheck": {
                "url": "https://nas.example/health", "expected_status": [200, 204]}}],
        }
        observed, evidence = doctor.endpoint_discovery(inventory, lambda url, timeout: 204)
        self.assertEqual(evidence["status"], "ok")
        self.assertEqual(observed["services"][0]["health"], "healthy")
        self.assertEqual(observed["storage"][0]["state"], "active")
        self.assertNotIn("example", str(observed))

    def test_endpoint_failure_becomes_component_finding_not_evidence_failure(self):
        inventory = {"services": [{"id": "app", "kind": "web", "healthcheck": {
            "url": "https://app.example/health", "expected_status": 200}}]}
        observed, evidence = doctor.endpoint_discovery(inventory, lambda url, timeout: 503)
        merged = doctor.merge_observations(inventory, observed)
        report = doctor.inspect_inventory(merged, [evidence])
        self.assertEqual(evidence["status"], "ok")
        self.assertIn("service-unhealthy", {finding["code"] for finding in report["findings"]})
        self.assertNotIn("evidence-gap", {finding["code"] for finding in report["findings"]})

    def test_reachability_probe_accepts_auth_response_without_claiming_health(self):
        inventory = {"services": [{"id": "admin", "kind": "web", "healthcheck": {
            "url": "https://admin.example", "mode": "reachability"}}]}
        observed, evidence = doctor.endpoint_discovery(inventory, lambda url, timeout: 401)
        self.assertEqual(evidence["status"], "ok")
        self.assertEqual(observed["services"][0]["health"], "reachable")

    def test_reachability_probe_reports_tls_trust_separately_from_outage(self):
        inventory = {"services": [{"id": "admin", "kind": "web", "healthcheck": {
            "url": "https://admin.example", "mode": "reachability"}}]}
        def probe(url, timeout):
            raise doctor.URLError(doctor.ssl.SSLCertVerificationError(1, "untrusted"))
        observed, _ = doctor.endpoint_discovery(inventory, probe)
        self.assertEqual(observed["services"][0]["health"], "reachable")
        self.assertEqual(observed["services"][0]["probe_status"], "reachable-with-tls-error")

    def test_endpoint_probe_rejects_embedded_credentials_and_missing_env(self):
        inventory = {"services": [
            {"id": "bad", "kind": "web", "healthcheck": {"url": "https://user:pass@example/health"}},
            {"id": "missing", "kind": "web", "healthcheck": {"url_env": "DOES_NOT_EXIST"}},
        ]}
        with patch.dict(doctor.os.environ, {}, clear=True):
            observed, evidence = doctor.endpoint_discovery(inventory, lambda url, timeout: 200)
        self.assertEqual(observed["services"], [])
        self.assertEqual(evidence["status"], "partial")
        self.assertNotIn("user", evidence["detail"])

    def test_probe_details_are_not_persisted_in_history(self):
        inventory = {"services": [{"id": "app", "kind": "web", "health": "healthy",
                                    "healthcheck": {"url": "https://private.example/secret"}}]}
        snapshot = doctor.make_snapshot(inventory, "2026-01-01T00:00:00Z")
        self.assertNotIn("private.example", str(snapshot))

    @patch.object(doctor.shutil, "which", return_value="/usr/bin/docker")
    def test_docker_discovers_compose_dependencies_stacks_and_networks(self, _which):
        ps = "\n".join([
            '{"ID":"1","Names":"media-jellyfin-1","Image":"jellyfin:latest","Status":"Up","Ports":""}',
            '{"ID":"2","Names":"media-db-1","Image":"postgres:16","Status":"Up","Ports":""}',
        ])
        inspected = doctor.json.dumps([
            {"Name": "/media-jellyfin-1", "State": {"Status": "running"}, "Mounts": [],
             "Config": {"Labels": {"com.docker.compose.project": "media", "com.docker.compose.service": "jellyfin",
                                     "com.docker.compose.depends_on": "db:service_healthy:false"}},
             "NetworkSettings": {"Networks": {"media_default": {"Gateway": "172.20.0.1"}}}},
            {"Name": "/media-db-1", "State": {"Status": "running"}, "Mounts": [],
             "Config": {"Labels": {"com.docker.compose.project": "media", "com.docker.compose.service": "db"}},
             "NetworkSettings": {"Networks": {"media_default": {"Gateway": "172.20.0.1"}}}},
        ])
        def runner(command, timeout=10):
            return (0, ps, "") if command[1] == "ps" else (0, inspected, "")
        inventory, _ = doctor.docker_discovery(runner)
        graph = doctor.infer_topology(inventory)
        edges = {(edge.source, edge.relation, edge.target) for edge in doctor.build_edges(graph)}
        self.assertIn(("media-jellyfin-1", "depends_on", "media-db-1"), edges)
        self.assertIn(("media-jellyfin-1", "member_of", "compose-stack:media"), edges)
        self.assertIn(("media-jellyfin-1", "connected_to", "docker-network:media_default"), edges)
        self.assertEqual(len(graph["stacks"]), 1)
        self.assertEqual(len(graph["network_segments"]), 1)

    def test_infers_jellyfin_nfs_nas_vm_proxmox_chain(self):
        df = "Filesystem 1024-blocks Used Available Capacity Mounted on\nnas01:/media 100 50 50 50% /mnt/media\n"
        mounts = "nas01:/media on /mnt/media (nfs, nodev)\n"
        def runner(command, timeout=10):
            return (0, df, "") if command[0] == "df" else (0, mounts, "")
        host_storage, _ = doctor.host_storage_discovery(runner)
        host_storage["storage"][0]["mounted_by"] = ["docker-host"]
        inventory = doctor.merge_inventory({
            "nodes": [{"id": "pve-01", "role": "proxmox"}],
            "services": [
                {"id": "nas01", "kind": "proxmox-qemu", "runs_on": "pve-01"},
                {"id": "jellyfin", "kind": "docker-container", "runs_on": "docker-host",
                 "bind_sources": ["/mnt/media/movies"]},
            ],
        }, host_storage)
        graph = doctor.infer_topology(inventory)
        remote = next(item for item in graph["storage"] if item["kind"] == "nfs")
        edges = {(edge.source, edge.relation, edge.target) for edge in doctor.build_edges(graph)}
        self.assertIn(("jellyfin", "uses", remote["id"]), edges)
        self.assertIn((remote["id"], "served_by", "nas01"), edges)
        self.assertIn(("nas01", "runs_on", "pve-01"), edges)
        self.assertEqual(graph["unresolved_relationships"], [])

    def test_unmatched_bind_and_storage_server_are_reported_as_unknown(self):
        inventory = {"services": [{"id": "app", "kind": "docker-container", "bind_sources": ["/mystery/data"]}],
                     "storage": [{"id": "remote", "kind": "nfs", "server_host": "unknown-nas", "mounted_by": []}]}
        graph = doctor.infer_topology(inventory)
        report = doctor.inspect_inventory(graph)
        self.assertEqual(report["summary"]["unresolved_relationships"], 2)
        self.assertTrue(any("Unresolved uses_storage" in item for item in report["unknowns"]))
        self.assertTrue(any(node["id"] == "discovered-host:unknown-nas" for node in graph["nodes"]))

    def test_diagnostic_bundle_contains_only_redacted_derived_artifacts(self):
        report = doctor.inspect_inventory({"homelab": {"name": "lab 192.168.1.10"}, "nodes": []}, [{
            "source": "docker", "status": "unavailable", "detail": "unix:///Users/alice/.docker/run.sock"}])
        doctor.attach_recovery_readiness(report, {"services": []})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle"
            files = doctor.create_diagnostic_bundle(report, output)
            self.assertEqual(set(files), {"report.md", "report.json", "manifest.json", "README.md"})
            combined = "\n".join((output / name).read_text(encoding="utf-8") for name in files)
            self.assertNotIn("192.168.1.10", combined)
            self.assertNotIn("alice", combined)
            self.assertNotIn("raw inventory", (output / "report.json").read_text(encoding="utf-8"))
            parsed = doctor.json.loads((output / "report.json").read_text(encoding="utf-8"))
            self.assertTrue(parsed["read_only"])
            manifest = doctor.json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("credentials", manifest["excluded"])

    def test_diagnostic_bundle_refuses_nonempty_directory(self):
        report = doctor.inspect_inventory({"homelab": {"name": "lab"}, "nodes": []})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "user-file.txt").write_text("preserve", encoding="utf-8")
            with self.assertRaises(ValueError):
                doctor.create_diagnostic_bundle(report, output)
            self.assertEqual((output / "user-file.txt").read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()
