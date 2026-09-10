"""No network is used. Fake Cloudflare is only a contract test double."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cf = load_module("cloudflare_onboard", "cloudflare_onboard.py")
br = load_module("backup_restore", "backup_restore.py")


class FakeCloudflare:
    def __init__(self, records):
        self.rows = copy.deepcopy(records)
        self.writes = []
        self.zone_name = "kuanguard.com"
        self.unknown_post = False

    def zone(self, config):
        cf.check_target(config)
        if self.zone_name != config["apex"]:
            raise cf.Refusal("wrong live zone")
        return {"name": self.zone_name, "id": config["zone_id"], "account": {"id": config["account_id"]}, "name_servers": [], "status": "pending"}

    def records(self, config):
        return copy.deepcopy(self.rows)

    def request(self, method, path, payload=None, raw=False):
        if raw:
            return b"; synthetic complete candidate-zone export for unit test only\n$ORIGIN kuanguard.com.\n"
        if method == "POST":
            self.writes.append((method, path, copy.deepcopy(payload)))
            result = {**copy.deepcopy(payload), "id": f"{1000 + len(self.writes):032x}", "modified_on": "2026-09-10T00:00:00Z"}
            self.rows.append(result)
            if self.unknown_post:
                raise cf.Refusal("simulated accepted-write / lost-response")
        elif method == "PATCH":
            self.writes.append((method, path, copy.deepcopy(payload)))
            result = next(row for row in self.rows if row["id"] == path.rsplit("/", 1)[1])
            result.update(copy.deepcopy(payload))
        elif method == "DELETE":
            self.writes.append((method, path, None))
            self.rows = [row for row in self.rows if row["id"] != path.rsplit("/", 1)[1]]
            result = {"id": path.rsplit("/", 1)[1]}
        else:
            result = {}
        return {"success": True, "result": copy.deepcopy(result)}


class CloudflareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = {"apex": "kuanguard.com", "account_id": "a" * 32, "zone_id": "b" * 32,
                       "managed_records": [{"key": "app", "name": "app.kuanguard.com", "type": "CNAME", "content": "synthetic-origin.hosting.net", "ttl": 1, "proxied": False}]}
        self.protected = [
            {"id": f"{index:032x}", "name": "kuanguard.com" if kind != "SRV" else "_sip._tcp.kuanguard.com", "type": kind, "content": content, "ttl": 3600, "tags": [], "data": data}
            for index, (kind, content, data) in enumerate([
                ("MX", "mail.kuanguard.com", {}), ("TXT", "v=spf1 include:mail.host.test -all", {}),
                ("CAA", '0 issue "letsencrypt.org"', {"flags": 0, "tag": "issue", "value": "letsencrypt.org"}),
                ("SRV", "5 443 sip.host.test", {"priority": 10, "port": 443}),
            ], 1)
        ]
        self.api = FakeCloudflare(self.protected)
        export = self.root / "authority.bind"
        export.write_text("synthetic original authority zone export", encoding="utf-8")
        reconcile = self.root / "reconcile.json"
        reconcile.write_text('{"synthetic": true, "all_preserved": true}', encoding="utf-8")
        self.proof = {"apex": cf.APEX, "provider": "test", "complete_zone_export": True,
                      "reviewed_by": "unit-test-only", "captured_at": cf.now(), "authoritative_nameservers": ["ns.test"],
                      "parent_ds_records": [], "reconciled_into_cloudflare": True,
                      "zone_export": {"path": str(export), "sha256": cf.file_hash(export)},
                      "reconciliation_evidence": {"path": str(reconcile), "sha256": cf.file_hash(reconcile)}}

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, folder="inspect"):
        snapshot = cf.inspect_zone(self.api, self.config, self.root / folder)
        return cf.build_plan(self.config, snapshot, self.proof)

    def test_roundtrip_preserves_mx_txt_caa_srv_and_second_plan_is_empty(self):
        plan = self.plan()
        self.assertEqual([a["operation"] for a in plan["actions"]], ["create"])
        receipt = cf.apply_plan(self.api, plan, plan["plan_sha256"], self.root / "receipt.json")
        self.assertEqual(self.api.rows[:4], self.protected)
        second = self.plan("inspect2")
        self.assertEqual(second["actions"], [])
        cf.rollback(self.api, receipt, receipt["receipt_sha256"], self.root / "rollback.json")
        self.assertEqual(self.api.rows, self.protected)
        self.assertTrue(all("/dns_records" in row[1] for row in self.api.writes))

    def test_account_zone_drift_refuses_before_any_write(self):
        plan = self.plan()
        self.api.zone_name = "other-domain.test"
        with self.assertRaises(cf.Refusal):
            cf.apply_plan(self.api, plan, plan["plan_sha256"], self.root / "receipt.json")
        self.assertEqual(self.api.writes, [])

    def test_free_zone_two_apex_addresses_roundtrip_without_paid_tags(self):
        self.config["managed_records"] = [
            {"key": f"apex-{index}", "name": cf.APEX, "type": "A", "content": ip,
             "ttl": 300, "proxied": False, "ownership_mode": "comment"}
            for index, ip in enumerate(("216.150.1.1", "216.150.16.1"), 1)
        ]
        request = self.api.request
        def free_request(method, path, payload=None, raw=False):
            if payload and payload.get("tags"):
                raise cf.Refusal("Free zones do not support record tags")
            return request(method, path, payload, raw)
        self.api.request = free_request
        plan = self.plan()
        self.assertEqual(len(plan["actions"]), 2)
        receipt = cf.apply_plan(self.api, plan, plan["plan_sha256"], self.root / "receipt.json")
        self.assertEqual(self.plan("inspect2")["actions"], [])
        self.assertEqual(self.api.rows[:4], self.protected)
        cf.rollback(self.api, receipt, receipt["receipt_sha256"], self.root / "rollback.json")
        self.assertEqual(self.api.rows, self.protected)

    def test_comment_adoption_preserves_existing_text_and_restores_on_rollback(self):
        existing = {"id": "e" * 32, "name": "app.kuanguard.com", "type": "CNAME", "content": "previous.host.test",
                    "ttl": 60, "proxied": False, "comment": "keep this note", "tags": []}
        self.api.rows.append(copy.deepcopy(existing))
        self.config["managed_records"][0].update(ownership_mode="comment", adopt_id=existing["id"], adopt_sha256=cf.digest(existing))
        plan = self.plan()
        receipt = cf.apply_plan(self.api, plan, plan["plan_sha256"], self.root / "receipt.json")
        self.assertEqual(self.api.rows[-1]["comment"], "keep this note | kuanguard-managed:app")
        self.assertEqual(self.plan("inspect2")["actions"], [])
        self.api.rows[-1]["comment"] += " changed"
        with self.assertRaises(cf.Refusal):
            cf.rollback(self.api, receipt, receipt["receipt_sha256"], self.root / "changed.json")
        self.api.rows[-1]["comment"] = receipt["operations"][0]["result"]["comment"]
        cf.rollback(self.api, receipt, receipt["receipt_sha256"], self.root / "rollback.json")
        self.assertEqual(self.api.rows[-1], existing)

    def test_comment_ownership_does_not_allow_protected_deletes_or_truncate_notes(self):
        self.api.rows[0]["comment"] = "kuanguard-managed:mail"
        self.config["managed_records"] = [{"key": "mail", "state": "absent"}]
        with self.assertRaises(cf.Refusal):
            self.plan()
        item = {"key": "app", "name": "app.kuanguard.com", "type": "A", "content": "216.150.1.1", "ttl": 300,
                "proxied": False, "ownership_mode": "comment"}
        with self.assertRaises(cf.Refusal):
            cf.desired_payload(item, {"comment": "x" * 100})
        self.config["managed_records"] = [item, {**item, "key": "duplicate"}]
        with self.assertRaises(cf.Refusal):
            self.plan("duplicates")

    def test_unmanaged_drift_refuses_before_any_write(self):
        plan = self.plan()
        self.api.rows[0]["ttl"] = 60
        with self.assertRaises(cf.Refusal):
            cf.apply_plan(self.api, plan, plan["plan_sha256"], self.root / "receipt.json")
        self.assertEqual(self.api.writes, [])

    def test_hash_tamper_and_expiry_refused(self):
        plan = self.plan()
        changed = copy.deepcopy(plan)
        changed["actions"][0]["after"]["content"] = "unauthorized.host.test"
        cf.seal(changed, "plan_sha256")
        with self.assertRaises(cf.Refusal):
            cf.apply_plan(self.api, changed, changed["plan_sha256"], self.root / "tamper.json")
        old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        expired = cf.build_plan(self.config, plan["snapshot"], self.proof, created_at=old)
        with self.assertRaises(cf.Refusal):
            cf.apply_plan(self.api, expired, expired["plan_sha256"], self.root / "expired.json")
        with self.assertRaises(cf.Refusal):
            cf.apply_plan(self.api, plan, "0" * 64, self.root / "bad-hash.json")
        self.assertEqual(self.api.writes, [])

    def test_real_target_full_export_and_allowlist_are_required(self):
        for change in ({"name": "sim.kuanguard.com"}, {"type": "MX"}, {"content": "<provider target>"},
                       {"type": "A", "content": "192.0.2.10"}, {"name": "unrelated.com"}, {"proxied": True}):
            with self.subTest(change=change):
                item = {**self.config["managed_records"][0], **change}
                with self.assertRaises(cf.Refusal):
                    cf.desired_payload(item, None)
        plan = self.plan()
        self.proof["complete_zone_export"] = False
        with self.assertRaises(cf.Refusal):
            cf.build_plan(self.config, plan["snapshot"], self.proof)
        self.proof["complete_zone_export"] = True
        Path(self.proof["zone_export"]["path"]).write_text("tampered")
        with self.assertRaises(cf.Refusal):
            cf.build_plan(self.config, plan["snapshot"], self.proof)

    def test_existing_record_needs_explicit_adoption_and_rollback_restores_tags(self):
        existing = {"id": "e" * 32, "name": "app.kuanguard.com", "type": "CNAME", "content": "previous.host.test", "ttl": 60, "proxied": False, "comment": "preserve me", "tags": ["existing:tag"]}
        self.api.rows.append(copy.deepcopy(existing))
        snapshot = cf.inspect_zone(self.api, self.config, self.root / "inspect")
        with self.assertRaises(cf.Refusal):
            cf.build_plan(self.config, snapshot, self.proof)
        self.config["managed_records"][0].update({"adopt_id": existing["id"], "adopt_sha256": cf.digest(existing)})
        plan = cf.build_plan(self.config, snapshot, self.proof)
        receipt = cf.apply_plan(self.api, plan, plan["plan_sha256"], self.root / "receipt.json")
        self.assertEqual(self.api.rows[-1]["comment"], "preserve me")
        self.assertEqual(self.plan("inspect2")["actions"], [])
        cf.rollback(self.api, receipt, receipt["receipt_sha256"], self.root / "rollback.json")
        self.assertEqual(self.api.rows[-1], existing)

    def test_unknown_mutation_is_journaled_and_cannot_blindly_retry_or_rollback(self):
        plan = self.plan()
        self.api.unknown_post = True
        with self.assertRaises(cf.Refusal):
            cf.apply_plan(self.api, plan, plan["plan_sha256"], self.root / "receipt.json")
        receipt = cf.read_json(self.root / "receipt.json")
        self.assertEqual(receipt["state"], "needs_reconciliation")
        self.assertEqual(receipt["operations"][0]["state"], "prepared")
        with self.assertRaises(cf.Refusal):
            cf.rollback(self.api, receipt, receipt["receipt_sha256"], self.root / "rollback.json")
        with self.assertRaises(cf.Refusal):
            cf.apply_plan(self.api, plan, plan["plan_sha256"], self.root / "retry.json")
        self.assertEqual(len(self.api.writes), 1)

    def test_rollback_refuses_subsequent_managed_change(self):
        plan = self.plan()
        receipt = cf.apply_plan(self.api, plan, plan["plan_sha256"], self.root / "receipt.json")
        self.api.rows[-1]["content"] = "changed-by-operator.host.test"
        with self.assertRaises(cf.Refusal):
            cf.rollback(self.api, receipt, receipt["receipt_sha256"], self.root / "rollback.json")
        self.assertEqual(len(self.api.writes), 1)

    def test_explicit_owned_delete_recreates_only_that_record(self):
        owned = {"id": "d" * 32, "name": "status.kuanguard.com", "type": "CNAME", "content": "old.host.test", "ttl": 1, "proxied": True, "tags": [cf.MANAGED_PREFIX + "status"]}
        self.api.rows.append(owned)
        self.config["managed_records"] = [{"key": "status", "state": "absent"}]
        plan = self.plan()
        receipt = cf.apply_plan(self.api, plan, plan["plan_sha256"], self.root / "receipt.json")
        self.assertEqual(self.api.rows, self.protected)
        cf.rollback(self.api, receipt, receipt["receipt_sha256"], self.root / "rollback.json")
        self.assertEqual(cf.record_payload(self.api.rows[-1]), cf.record_payload(owned))

    def test_badly_tagged_mail_record_cannot_be_deleted(self):
        self.api.rows[0]["tags"] = [cf.MANAGED_PREFIX + "mail"]
        self.config["managed_records"] = [{"key": "mail", "state": "absent"}]
        with self.assertRaises(cf.Refusal):
            self.plan()

    def test_paginated_inventory_requires_every_unique_record(self):
        api = object.__new__(cf.CloudflareAPI)
        replies = [
            {"result": self.protected[:2], "result_info": {"total_count": 4, "total_pages": 2}},
            {"result": self.protected[2:], "result_info": {"total_count": 4, "total_pages": 2}},
        ]
        api.request = lambda *args: replies.pop(0)
        self.assertEqual(api.records(self.config), self.protected)
        api.request = lambda *args: {"result": self.protected[:2], "result_info": {"total_count": 4, "total_pages": 1}}
        with self.assertRaises(cf.Refusal):
            api.records(self.config)
        api.request = lambda *args: {"result": self.protected[:1] * 2, "result_info": {"total_count": 2, "total_pages": 1}}
        with self.assertRaises(cf.Refusal):
            api.records(self.config)

    def test_vercel_hosts_are_dns_only_and_admin_requires_actual_tunnel(self):
        entry = self.config["managed_records"][0]
        for hostname in (cf.APEX, "www." + cf.APEX, "app." + cf.APEX):
            with self.subTest(hostname=hostname):
                with self.assertRaises(cf.Refusal):
                    cf.desired_payload({**entry, "name": hostname, "proxied": True}, None)
                self.assertFalse(cf.desired_payload({**entry, "name": hostname, "proxied": False}, None)["proxied"])
        with self.assertRaises(cf.Refusal):
            cf.desired_payload({**entry, "name": "assets.kuanguard.com", "content": "cname.vercel-dns-017.com", "proxied": True}, None)
        for target in ("direct-origin.hosting.net", "admin.vercel.app", "placeholder.cfargotunnel.com"):
            with self.subTest(target=target), self.assertRaises(cf.Refusal):
                cf.desired_payload({**entry, "name": "admin.kuanguard.com", "content": target, "proxied": True}, None)
        tunnel = "00000000-0000-4000-8000-000000000001.cfargotunnel.com"
        self.assertTrue(cf.desired_payload({**entry, "name": "admin.kuanguard.com", "content": tunnel, "proxied": True}, None)["proxied"])

    def test_transport_blocks_zone_settings_foreign_discovery_and_unbound_writes(self):
        api = cf.CloudflareAPI("synthetic-token-never-sent")
        class NoNetwork:
            def open(self, *args, **kwargs):
                raise AssertionError("Network must not be reached")
        api.opener = NoNetwork()
        zone = "/zones/" + self.config["zone_id"]
        for method, path in (("DELETE", zone), ("POST", "/zones"), ("PATCH", zone + "/dnssec"),
                             ("GET", "/zones?name=qidaigo.com&account.id=" + "a" * 32 + "&per_page=50"),
                             ("GET", "/zones?name=kuanguard.com&name=qidaigo.com&account.id=" + "a" * 32 + "&per_page=50"),
                             ("GET", "https://foreign.invalid/zones/" + "b" * 32),
                             ("POST", zone + "/dns_records"), ("DELETE", zone + "/dns_records/" + "c" * 32)):
            with self.subTest(method=method, path=path), self.assertRaises(cf.Refusal):
                api.request(method, path, self.config["managed_records"][0] if method == "POST" else None)
        api._verified_zone_id = self.config["zone_id"]
        with self.assertRaises(cf.Refusal):
            api.request("POST", zone + "/dns_records", {"name": cf.APEX, "type": "MX"})
        with self.assertRaises(cf.Refusal):
            api.request("DELETE", "/zones/" + "d" * 32 + "/dns_records/" + "c" * 32)

    def test_discovery_records_pending_without_creating_a_fake_snapshot(self):
        api = cf.CloudflareAPI("synthetic-token-never-sent")
        requests = []
        def reply(method, path):
            requests.append((method, path))
            result = [] if path.startswith("/zones?") else {"status": "active"} if path.endswith("/tokens/verify") else {"id": self.config["account_id"]}
            return {"success": True, "result": result}
        api.request = reply
        config = {**self.config, "zone_id": None}
        result = cf.inspect_zone(api, config, self.root / "discovery")
        self.assertEqual(result["state"], "pending_action")
        self.assertFalse(result["ready_for_plan"])
        self.assertIsNone(result["visible_zone_id"])
        self.assertTrue((self.root / "discovery" / "discovery.json").is_file())
        self.assertFalse((self.root / "discovery" / "snapshot.json").exists())
        self.assertTrue(all(method == "GET" for method, path in requests))
        with self.assertRaises(cf.Refusal):
            cf.build_plan(config, result, self.proof)

    def test_live_target_readback_binds_client_to_immutable_account_and_zone(self):
        api = cf.CloudflareAPI("synthetic-token-never-sent")
        api.request = lambda method, path: {"result": {"id": self.config["zone_id"], "name": cf.APEX, "account": {"id": self.config["account_id"]}}}
        api.zone(self.config)
        for field in ("zone_id", "account_id"):
            with self.subTest(field=field), self.assertRaises(cf.Refusal):
                api.zone({**self.config, field: "d" * 32})


class GatewayPolicyTests(unittest.TestCase):
    def test_public_draft_path_allowlist_does_not_expose_internal_or_general_app_routes(self):
        config = (ROOT / "infra" / "gateway" / "public-api.conf").read_text(encoding="utf-8")
        match = re.search(r"location\s+~\s+(\S+)\s*\{", config)
        self.assertIsNotNone(match, "Public API must use an explicit route allowlist")
        route = re.compile(match.group(1))
        for path in ("/app/drafts/campaign/new", "/app/drafts/training/new", "/customer/projects", "/learner/enrollments", "/auth/me"):
            with self.subTest(path=path):
                self.assertIsNotNone(route.match(path))
        for path in ("/internal/projects", "/internal/cost-projects", "/development/jobs", "/app/admin", "/app/drafts-other/campaign/new", "/app/draftsinternal", "/application/drafts/campaign/new"):
            with self.subTest(path=path):
                self.assertIsNone(route.match(path))
        self.assertIn('proxy_set_header Cf-Access-Jwt-Assertion "";', config)
        self.assertIn("location ^~ /auth/dev/ { return 404; }", config)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.objects = self.root / "private"
        (self.objects / "tenant-a" / "reports").mkdir(parents=True)
        (self.objects / "tenant-a" / "reports" / "report.pdf").write_bytes(b"synthetic private PDF fixture")
        self.db = self.root / "source.sqlite3"
        connection = sqlite3.connect(self.db)
        connection.executescript("CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT); INSERT INTO jobs VALUES('job-1','pending'); CREATE TABLE ledger(id TEXT PRIMARY KEY,amount INTEGER); INSERT INTO ledger VALUES('ledger-1',42);")
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp.cleanup()

    def backup(self):
        return br.create_backup(self.root / "backup", self.objects, sqlite_path=self.db, writers_paused=True,
                                metadata={"apex": "kuanguard.com", "key_references": ["secret://backup/encryption-key-v1"]})

    def test_real_db_object_restore_and_persistent_jobs_survive(self):
        manifest = self.backup()
        receipt = br.restore_backup(self.root / "backup", self.root / "restores" / "one", manifest["manifest_sha256"], allowed_root=self.root / "restores")
        self.assertEqual(receipt["state"], "restored")
        db = sqlite3.connect(self.root / "restores" / "one" / "database.sqlite3")
        self.assertEqual(db.execute("SELECT state FROM jobs WHERE id='job-1'").fetchone(), ("pending",))
        self.assertEqual(db.execute("SELECT amount FROM ledger").fetchone(), (42,))
        db.close()
        self.assertEqual((self.root / "restores" / "one" / "objects" / "tenant-a" / "reports" / "report.pdf").read_bytes(), b"synthetic private PDF fixture")
        self.assertEqual(receipt["application_job_recovery"], "unverified_requires_application_reconciliation")

    def test_corruption_refused_before_restore_writes(self):
        manifest = self.backup()
        (self.root / "backup" / "objects" / "tenant-a" / "reports" / "report.pdf").write_bytes(b"corrupt")
        with self.assertRaises(br.BackupError):
            br.restore_backup(self.root / "backup", self.root / "restores" / "one", manifest["manifest_sha256"], allowed_root=self.root / "restores")
        self.assertFalse((self.root / "restores").exists())

    def test_restore_never_overwrites_or_escapes_allowed_root(self):
        manifest = self.backup()
        with self.assertRaises(br.BackupError):
            br.verify_backup(self.root / "backup", "0" * 64)
        existing = self.root / "restores" / "existing"
        existing.mkdir(parents=True)
        for target in (self.root / "outside", existing, self.root / "restores"):
            with self.subTest(target=target), self.assertRaises(br.BackupError):
                br.restore_backup(self.root / "backup", target, manifest["manifest_sha256"], allowed_root=self.root / "restores")

    def test_traversal_manifest_and_unrecorded_extra_file_refused(self):
        manifest = self.backup()
        for path in ("../outside", "objects/../../outside", "C:/escape", "objects\\escape", "/absolute"):
            with self.subTest(path=path), self.assertRaises(br.BackupError):
                br.contained_path(self.root / "backup", path)
        (self.root / "backup" / "unexpected.env").write_text("not accepted")
        with self.assertRaises(br.BackupError):
            br.verify_backup(self.root / "backup", manifest["manifest_sha256"])

    def test_pause_attestation_secret_references_and_destination_required(self):
        with self.assertRaises(br.BackupError):
            br.create_backup(self.root / "backup", self.objects, sqlite_path=self.db)
        with self.assertRaises(br.BackupError):
            br.create_backup(self.objects / "backup", self.objects, sqlite_path=self.db, writers_paused=True)
        with self.assertRaises(br.BackupError):
            br.validate_metadata({"database_password": "forbidden"})
        with self.assertRaises(br.BackupError):
            br.validate_metadata({"key_references": ["inline-key-material"]})

    def test_postgres_restore_refuses_live_database_before_commands(self):
        pg = br.PostgreSQL("kuanguard", "kuanguard")
        for target in ("kuanguard", "another_db", "kuanguard_restore_test;DROP DATABASE kuanguard"):
            with self.subTest(target=target), self.assertRaises(br.BackupError):
                pg.empty_restore_database(target)


if __name__ == "__main__":
    unittest.main()
