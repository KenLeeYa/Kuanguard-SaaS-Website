#!/usr/bin/env python3
"""Scoped Cloudflare DNS reconciliation. No registrar, zone deletion, or mail writes.

Only an explicitly reviewed, unexpired plan can mutate A/AAAA/CNAME records.
The official v4 API is the state source; no third-party SDK is required.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

APEX = "kuanguard.com"
API_BASE = "https://api.cloudflare.com/client/v4"
VERSION = "1.1.1"
MANAGED_PREFIX = "kuanguard-managed:"
ALLOWED_HOSTS = {APEX, *(f"{host}.{APEX}" for host in ("www", "app", "admin", "api", "assets", "status"))}
VERCEL_HOSTS = {APEX, "www." + APEX, "app." + APEX}
SAFE_TYPES = {"A", "AAAA", "CNAME"}
CONFIG_FIELDS = ("type", "name", "content", "ttl", "proxied", "comment", "tags", "settings", "priority", "data")


class Refusal(ValueError):
    """An explicit safety precondition has not been met."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def read_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict, *, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive and path.exists():
        raise Refusal(f"Evidence output already exists: {path}")
    temp = path.with_name(path.name + ".tmp")
    with temp.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def seal(value: dict, field: str) -> dict:
    value[field] = digest({k: v for k, v in value.items() if k != field})
    return value


def check_seal(value: dict, field: str):
    if value.get(field) != digest({k: v for k, v in value.items() if k != field}):
        raise Refusal(f"Integrity check failed: {field}")


def checked_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-fA-F0-9]{32}", value):
        raise Refusal(f"{label} must be an actual 32-character Cloudflare ID")
    return value


def check_target(config: dict):
    if config.get("apex") != APEX:
        raise Refusal(f"This tool is restricted to {APEX}")
    checked_id(config.get("account_id"), "account_id")
    checked_id(config.get("zone_id"), "zone_id")


def record_payload(record: dict) -> dict:
    payload = {key: record[key] for key in CONFIG_FIELDS if key in record}
    payload.setdefault("tags", [])
    return payload


def ownership_markers(record: dict) -> list[str]:
    comments = (record.get("comment") or "").split(" | ")
    return [value for value in record.get("tags", []) + comments if value.startswith(MANAGED_PREFIX)]


def records_hash(records: list[dict]) -> str:
    return digest(sorted(records, key=lambda item: item["id"]))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Refusal("Cloudflare API redirect refused; credentials must not leave the fixed API origin")


class CloudflareAPI:
    def __init__(self, token: str):
        if not token:
            raise Refusal("CLOUDFLARE_API_TOKEN is not configured; no request was made")
        self.token = token
        self.opener = build_opener(NoRedirect())
        self._verified_zone_id = None
        self._verified_account_id = None

    @staticmethod
    def check_endpoint(method: str, path: str):
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc or parsed.fragment:
            raise Refusal("Only relative paths on the fixed Cloudflare API origin are allowed")
        query = parse_qs(parsed.query, keep_blank_values=True)
        identifier = r"[a-fA-F0-9]{32}"
        if method == "GET":
            if parsed.path == "/zones" and set(query) == {"name", "account.id", "per_page"}:
                if (query["name"] == [APEX] and query["per_page"] == ["50"]
                        and len(query["account.id"]) == 1):
                    checked_id(query["account.id"][0], "account_id")
                    return
            if not query and re.fullmatch(rf"/accounts/{identifier}(?:/tokens/verify)?", parsed.path):
                return
            if not query and re.fullmatch(rf"/zones/{identifier}(?:/dns_records/export|/dnssec|/settings/ssl)?", parsed.path):
                return
            if re.fullmatch(rf"/zones/{identifier}/dns_records", parsed.path):
                if (set(query) == {"page", "per_page"} and query["per_page"] == ["100"]
                        and len(query["page"]) == 1 and re.fullmatch(r"[1-9][0-9]*", query["page"][0])):
                    return
        elif not query:
            if method == "POST" and re.fullmatch(rf"/zones/{identifier}/dns_records", parsed.path):
                return
            if method in {"PATCH", "DELETE"} and re.fullmatch(rf"/zones/{identifier}/dns_records/{identifier}", parsed.path):
                return
        raise Refusal("HTTP method / endpoint is outside the scoped DNS workflow")

    def request(self, method: str, path: str, payload=None, *, raw=False):
        self.check_endpoint(method, path)
        if method != "GET":
            if path.split("/")[2] != self._verified_zone_id:
                raise Refusal("A mutation requires this client's verified immutable KUANGUARD zone binding")
            if method != "DELETE" and (not isinstance(payload, dict) or payload.get("type") not in SAFE_TYPES
                                       or payload.get("name") not in ALLOWED_HOSTS):
                raise Refusal("Transport refuses writes outside application A / AAAA / CNAME records")
        elif payload is not None:
            raise Refusal("Read requests cannot carry a mutation payload")
        body = None if payload is None else json.dumps(payload).encode()
        req = Request(API_BASE + path, data=body, method=method, headers={
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
            "User-Agent": "KUANGUARD-onboard/" + VERSION,
        })
        try:
            with self.opener.open(req, timeout=30) as response:
                data = response.read()
        except HTTPError as exc:
            # Provider bodies may contain sensitive data; never emit the body or token.
            raise Refusal(f"Cloudflare API returned HTTP {exc.code}; no automatic mutation retry") from None
        except (URLError, TimeoutError, OSError):
            raise Refusal("Cloudflare response unavailable; mutation outcome may be unknown; inspect before retry") from None
        if raw:
            return data
        result = json.loads(data)
        if not result.get("success"):
            codes = [error.get("code") for error in result.get("errors", [])]
            raise Refusal(f"Cloudflare rejected request; error codes: {codes}")
        return result

    def zone(self, config: dict) -> dict:
        check_target(config)
        if self._verified_zone_id and (self._verified_zone_id != config["zone_id"] or self._verified_account_id != config["account_id"]):
            raise Refusal("A Cloudflare client cannot be rebound to a different account or zone")
        zone = self.request("GET", f"/zones/{config['zone_id']}")["result"]
        if (zone.get("name") != APEX or zone.get("id") != config["zone_id"]
                or zone.get("account", {}).get("id") != config["account_id"]):
            raise Refusal("Fresh account / zone / apex readback does not match the approved target")
        self._verified_zone_id = config["zone_id"]
        self._verified_account_id = config["account_id"]
        return zone

    def discover(self, config: dict) -> dict:
        if config.get("apex") != APEX:
            raise Refusal(f"This tool is restricted to {APEX}")
        account_id = checked_id(config.get("account_id"), "account_id")
        account = self.request("GET", f"/accounts/{account_id}")["result"]
        if account.get("id") != account_id:
            raise Refusal("Cloudflare account readback does not match the configured account")
        token_status = "unverified"
        try:
            token_status = self.request("GET", f"/accounts/{account_id}/tokens/verify")["result"].get("status", "unverified")
        except Refusal:
            # A user token may read the account without using the account-token endpoint.
            pass
        response = self.request("GET", "/zones?" + urlencode({"name": APEX, "account.id": account_id, "per_page": 50}))
        zones = response["result"]
        if len(zones) > 1 or any(zone.get("name") != APEX or zone.get("account", {}).get("id") != account_id for zone in zones):
            raise Refusal("Filtered zone discovery returned an ambiguous or foreign target")
        return {"schema_version": 1, "tool_version": VERSION, "observed_at": now(), "apex": APEX,
                "account_id": account_id, "account_readback": "success", "account_token_status": token_status,
                "state": "pending_action", "visible_zone_id": checked_id(zones[0]["id"], "zone_id") if zones else None,
                "reason": "Copy the verified zone ID into config and run full inspect" if zones else "No matching zone visible to this token; confirm scope or authorized zone onboarding",
                "ready_for_plan": False, "complete_zone_export": False, "writes_performed": 0,
                "note": "Scoped listing cannot prove that a zone is absent from every Cloudflare account"}

    def records(self, config: dict) -> list[dict]:
        checked_id(config["zone_id"], "zone_id")
        records, page, total = [], 1, None
        while True:
            result = self.request("GET", f"/zones/{config['zone_id']}/dns_records?" + urlencode({"page": page, "per_page": 100}))
            info = result.get("result_info", {})
            if not isinstance(info.get("total_count"), int) or not isinstance(info.get("total_pages"), int):
                raise Refusal("DNS pagination metadata missing; cannot prove complete inventory")
            if total is not None and total != info["total_count"]:
                raise Refusal("DNS inventory changed during pagination; repeat inspect")
            total = info["total_count"]
            records.extend(result["result"])
            if page >= info["total_pages"]:
                break
            page += 1
        if len(records) != total or len({record["id"] for record in records}) != total:
            raise Refusal("Incomplete or duplicate DNS inventory")
        return records


def inspect_zone(api, config: dict, directory: Path) -> dict:
    if directory.exists():
        raise Refusal("Inspect needs a new evidence directory; existing evidence is preserved")
    if not config.get("zone_id"):
        result = api.discover(config)
        write_json(directory / "discovery.json", result, exclusive=True)
        return result
    check_target(config)
    zone = api.zone(config)
    before = api.records(config)
    export = api.request("GET", f"/zones/{config['zone_id']}/dns_records/export", raw=True)
    after = api.records(config)
    api.zone(config)
    if records_hash(before) != records_hash(after) or not export.strip():
        raise Refusal("Zone changed during export or export is empty; repeat inspect")
    directory.mkdir(parents=True)
    export_path = directory / "cloudflare-zone.bind"
    export_path.write_bytes(export)
    snapshot = seal({
        "schema_version": 1, "tool_version": VERSION, "observed_at": now(), "source": "cloudflare_api_v4",
        "apex": APEX, "account_id": config["account_id"], "zone_id": config["zone_id"],
        "zone_status": zone.get("status"), "assigned_nameservers": zone.get("name_servers", []),
        "records": after, "records_sha256": records_hash(after),
        "cloudflare_export": {"path": str(export_path.resolve()), "sha256": file_hash(export_path)},
        "complete_authoritative_export_proven": False,
    }, "snapshot_sha256")
    write_json(directory / "snapshot.json", snapshot)
    return snapshot


def validate_backup(proof: dict):
    required = ("provider", "reviewed_by", "captured_at", "reconciliation_evidence")
    if proof.get("apex") != APEX or proof.get("complete_zone_export") is not True:
        raise Refusal("Complete current-authoritative zone export attestation is required")
    if proof.get("reconciled_into_cloudflare") is not True:
        raise Refusal("Current authoritative records must first be reconciled into the candidate Cloudflare zone")
    if any(not proof.get(key) for key in required) or not proof.get("authoritative_nameservers"):
        raise Refusal("Authority, reviewer, timestamp, nameservers and reconciliation evidence are required")
    if "parent_ds_records" not in proof or not isinstance(proof["parent_ds_records"], list):
        raise Refusal("Parent DS inventory is required; an empty list must reflect a verified observation")
    for field in ("zone_export", "reconciliation_evidence"):
        item = proof[field]
        path = Path(item["path"])
        if not path.is_file() or not path.stat().st_size or file_hash(path) != item.get("sha256"):
            raise Refusal(f"Missing or modified backup evidence: {field}")


def desired_payload(item: dict, before: dict | None) -> dict:
    name = str(item.get("name", "")).lower().rstrip(".")
    if name not in ALLOWED_HOSTS:
        raise Refusal("Record name is outside the explicit public application hostname allowlist")
    record_type = item.get("type")
    if record_type not in SAFE_TYPES:
        raise Refusal("Only A / AAAA / CNAME application records are managed; MX/TXT/CAA/SRV/NS are preserved")
    content = item.get("content")
    if not isinstance(content, str) or not content or any(mark in content.lower() for mark in ("placeholder", "replace", "example", "<", ">")):
        raise Refusal("An actual provider-issued origin target is required")
    if record_type in {"A", "AAAA"}:
        try:
            address = ipaddress.ip_address(content)
        except ValueError:
            raise Refusal("Invalid origin IP") from None
        if address.version != (4 if record_type == "A" else 6) or not address.is_global:
            raise Refusal("Origin IP must be a public address of the declared family; test/private addresses are refused")
    else:
        content = content.lower().rstrip(".")
        if content.endswith((".test", ".invalid", ".localhost", ".example")):
            raise Refusal("Reserved test hostnames cannot be used as provider origins")
        if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}", content):
            raise Refusal("CNAME target must be a valid fully qualified provider hostname")
        if content == name:
            raise Refusal("CNAME must not point to itself")
    ttl, proxied = item.get("ttl", 1), item.get("proxied")
    if type(ttl) is not int or (ttl != 1 and not 60 <= ttl <= 86400) or type(proxied) is not bool:
        raise Refusal("TTL must be 1 or 60..86400; proxied must be an explicit boolean")
    if proxied and ttl != 1:
        raise Refusal("Use automatic TTL=1 for proxied records")
    vercel_target = content.endswith(".vercel.app") or bool(re.search(r"\.vercel-dns(?:-[a-z0-9]+)?\.com$", content))
    if proxied and (name in VERCEL_HOSTS or vercel_target or item.get("deployment_target") == "vercel"):
        raise Refusal("Vercel public/customer/learner hosts must be DNS-only (proxied=false)")
    if name == "admin." + APEX and (record_type != "CNAME" or not proxied or not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\.cfargotunnel\.com", content)):
        raise Refusal("admin.kuanguard.com requires its actual Cloudflare Tunnel CNAME and proxied=true; no public admin origin")
    key = item.get("key", "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", key):
        raise Refusal("Each managed record needs a stable key")
    payload = {"type": record_type, "name": name, "content": content, "ttl": ttl, "proxied": proxied}
    marker = MANAGED_PREFIX + key
    mode = item.get("ownership_mode", "tag")
    if mode == "comment":
        comment = (before or {}).get("comment") or ""
        if marker not in comment.split(" | "):
            comment = " | ".join(filter(None, (comment, marker)))
        if len(comment) > 100:
            raise Refusal("Ownership comment would exceed the Cloudflare Free 100-character limit; existing text is preserved")
        payload["comment"] = comment
    elif mode == "tag":
        payload["tags"] = sorted(set((before or {}).get("tags", []) + [marker]))
    else:
        raise Refusal("ownership_mode must be tag or comment")
    # PATCH preserves metadata outside the declared fields and ownership marker.
    return payload


def build_plan(config: dict, snapshot: dict, authority: dict, *, created_at=None) -> dict:
    check_target(config)
    check_seal(snapshot, "snapshot_sha256")
    validate_backup(authority)
    if snapshot.get("source") != "cloudflare_api_v4":
        raise Refusal("Plan requires an inspect receipt from the official Cloudflare API")
    for field in ("apex", "account_id", "zone_id"):
        if snapshot.get(field) != config[field]:
            raise Refusal("Config and snapshot target mismatch")
    records = snapshot["records"]
    if records_hash(records) != snapshot["records_sha256"]:
        raise Refusal("Snapshot records hash mismatch")
    export = snapshot["cloudflare_export"]
    if file_hash(Path(export["path"])) != export["sha256"]:
        raise Refusal("Cloudflare export changed")
    actions, used_keys, used_records = [], set(), set()
    desired = config.get("managed_records")
    if not isinstance(desired, list) or not desired:
        raise Refusal("No actual provider-issued targets configured; an empty template is not a ready plan")
    for item in desired:
        key = item.get("key", "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", key) or key in used_keys:
            raise Refusal("Managed keys must be valid and unique")
        used_keys.add(key)
        owned = [record for record in records if MANAGED_PREFIX + key in ownership_markers(record)]
        if len(owned) > 1:
            raise Refusal("Duplicate managed ownership; resolve inventory before planning")
        before = owned[0] if owned else None
        if item.get("state", "present") == "absent":
            if before:
                if before["type"] not in SAFE_TYPES or before["name"] not in ALLOWED_HOSTS:
                    raise Refusal("Protected record type/host cannot be deleted, including incorrectly tagged records")
                if before["id"] in used_records:
                    raise Refusal("One record cannot be controlled by multiple desired entries")
                used_records.add(before["id"])
                actions.append({"operation": "delete", "key": key, "before": before, "after": None})
            continue
        if item.get("state", "present") != "present":
            raise Refusal("Record state must be present or absent")
        if item.get("adopt_id"):
            checked_id(item["adopt_id"], "adopt_id")
            if before and before["id"] != item["adopt_id"]:
                raise Refusal("Adoption ID does not match current managed ownership")
            if not before:
                found = [record for record in records if record["id"] == item["adopt_id"]]
                if len(found) != 1 or digest(found[0]) != item.get("adopt_sha256"):
                    raise Refusal("Adoption requires an existing record ID and its exact inspected record hash")
                before = found[0]
                if ownership_markers(before):
                    raise Refusal("Record already belongs to another managed key")
        payload = desired_payload(item, before)
        if before:
            if before["id"] in used_records:
                raise Refusal("One record cannot be controlled by multiple desired entries")
            used_records.add(before["id"])
            if before["type"] not in SAFE_TYPES or before["name"] not in ALLOWED_HOSTS:
                raise Refusal("Protected record cannot be adopted or modified")
            if before["name"] != payload["name"] or before["type"] != payload["type"]:
                raise Refusal("Renaming or changing a record type requires a separate reviewed operation")
        for record in records:
            if before and record["id"] == before["id"]:
                continue
            if record["name"] == payload["name"] and (
                record["type"] in {"NS", "CNAME"} or payload["type"] == "CNAME"
                or (before is None and record["type"] == payload["type"])
            ):
                raise Refusal("Existing DNS name conflicts; records must be explicitly reconciled")
            if record["type"] == "MX" and record.get("content", "").rstrip(".").lower() == payload["name"] and payload["proxied"]:
                raise Refusal("An MX target must not be proxied as an HTTP origin")
        for action in actions:
            after = action.get("after")
            if after and after["name"] == payload["name"] and (
                "CNAME" in (after["type"], payload["type"])
                or (after["type"] == payload["type"] and after["content"] == payload["content"])
            ):
                raise Refusal("Desired entries contain conflicting DNS names")
        if not before or any(before.get(field) != value for field, value in payload.items()):
            actions.append({"operation": "update" if before else "create", "key": key, "before": before, "after": payload})
    created = datetime.fromisoformat(created_at) if created_at else datetime.now(timezone.utc)
    return seal({
        "schema_version": 1, "tool_version": VERSION, "created_at": created.isoformat(),
        "expires_at": (created + timedelta(minutes=30)).isoformat(),
        "config": config, "snapshot": snapshot, "authority_backup": authority,
        "actions": actions, "unmanaged_records_preserved": len(records) - len({action["before"]["id"] for action in actions if action["before"]}),
        "scope": "managed_application_dns_only", "registrar_ns_changes": False,
    }, "plan_sha256")


def validate_plan(plan: dict, expected_hash: str, *, check_expiry=True):
    check_seal(plan, "plan_sha256")
    if expected_hash != plan["plan_sha256"]:
        raise Refusal("Approval hash does not match this exact plan")
    rebuilt = build_plan(plan["config"], plan["snapshot"], plan["authority_backup"], created_at=plan["created_at"])
    if rebuilt != plan:
        raise Refusal("Plan actions do not match deterministic reconciliation")
    if check_expiry and datetime.now(timezone.utc) > datetime.fromisoformat(plan["expires_at"]):
        raise Refusal("Plan expired; inspect and plan again")


def apply_plan(api, plan: dict, expected_hash: str, receipt_path: Path) -> dict:
    validate_plan(plan, expected_hash)
    config = plan["config"]
    api.zone(config)
    if records_hash(api.records(config)) != plan["snapshot"]["records_sha256"]:
        raise Refusal("DNS drift since inspect; no changes were applied")
    receipt = {"schema_version": 1, "plan_sha256": expected_hash, "target": {k: config[k] for k in ("apex", "account_id", "zone_id")},
               "started_at": now(), "state": "running", "operations": []}
    write_json(receipt_path, seal(receipt, "receipt_sha256"), exclusive=True)
    expected_records = list(plan["snapshot"]["records"])
    try:
        for action in plan["actions"]:
            # A fresh read before every mutation catches drift and retains all unrelated records.
            api.zone(config)
            if records_hash(api.records(config)) != records_hash(expected_records):
                raise Refusal("DNS changed during apply; remaining operations were stopped")
            operation = {**action, "state": "prepared", "prepared_at": now()}
            receipt["operations"].append(operation)
            write_json(receipt_path, seal(receipt, "receipt_sha256"))
            before = action["before"]
            path = f"/zones/{config['zone_id']}/dns_records"
            if action["operation"] == "create":
                result = api.request("POST", path, action["after"])["result"]
                expected_records.append(result)
            elif action["operation"] == "update":
                result = api.request("PATCH", path + "/" + checked_id(before["id"], "record_id"), action["after"])["result"]
                expected_records = [result if row["id"] == before["id"] else row for row in expected_records]
            else:
                api.request("DELETE", path + "/" + checked_id(before["id"], "record_id"))
                result = None
                expected_records = [row for row in expected_records if row["id"] != before["id"]]
            operation.update({"state": "confirmed", "confirmed_at": now(), "result": result})
            write_json(receipt_path, seal(receipt, "receipt_sha256"))
        after = api.records(config)
        if records_hash(after) != records_hash(expected_records):
            raise Refusal("Post-apply readback drift; inspect receipt and do not blindly retry")
        receipt.update({"state": "succeeded", "completed_at": now(), "after_records_sha256": records_hash(after)})
    except Exception:
        receipt.update({"state": "needs_reconciliation", "stopped_at": now(),
                        "note": "Prepared operations may have reached provider; inspect before any retry or rollback."})
        write_json(receipt_path, seal(receipt, "receipt_sha256"))
        raise
    write_json(receipt_path, seal(receipt, "receipt_sha256"))
    return receipt


def rollback(api, receipt: dict, expected_hash: str, output: Path) -> dict:
    check_seal(receipt, "receipt_sha256")
    if expected_hash != receipt["receipt_sha256"]:
        raise Refusal("Rollback approval must match the exact apply receipt hash")
    if any(item["state"] != "confirmed" for item in receipt["operations"]):
        raise Refusal("An operation outcome is unknown; reconcile it before rollback")
    config = receipt["target"]
    api.zone(config)
    records = api.records(config)
    by_id = {record["id"]: record for record in records}
    for item in receipt["operations"]:
        before, result = item["before"], item["result"]
        if item["operation"] not in {"create", "update", "delete"}:
            raise Refusal("Unknown receipt operation")
        if (item["operation"] == "create" and (before is not None or not result)
                or item["operation"] == "update" and (not before or not result)
                or item["operation"] == "delete" and (not before or result is not None)):
            raise Refusal("Receipt operation shape is invalid")
        target = result or before
        if target["type"] not in SAFE_TYPES or target["name"] not in ALLOWED_HOSTS:
            raise Refusal("Rollback cannot touch protected records")
        if before and (before["type"] not in SAFE_TYPES or before["name"] not in ALLOWED_HOSTS):
            raise Refusal("Rollback prior value is a protected record")
        if before and result and any(before[field] != result[field] for field in ("id", "type", "name")):
            raise Refusal("Rollback cannot rename or change the type of a record")
        if result:
            if digest(by_id.get(result["id"])) != digest(result) or MANAGED_PREFIX + item["key"] not in ownership_markers(result):
                raise Refusal("Managed record changed after apply; rollback refused to overwrite it")
        elif any(record["name"] == before["name"] and (before["type"] == "CNAME" or record["type"] in {before["type"], "CNAME", "NS"}) for record in records):
            raise Refusal("Deleted record name was reused; rollback requires a new conflict review")
        if before and item["operation"] == "delete" and MANAGED_PREFIX + item["key"] not in ownership_markers(before):
            raise Refusal("Rollback will only recreate explicitly owned deleted records")
    log = {"schema_version": 1, "source_receipt_sha256": expected_hash, "target": config, "started_at": now(), "state": "running", "operations": []}
    write_json(output, seal(log, "rollback_sha256"), exclusive=True)
    expected_records = records
    try:
        for item in reversed(receipt["operations"]):
            api.zone(config)
            if records_hash(api.records(config)) != records_hash(expected_records):
                raise Refusal("DNS drift during rollback; inspect before continuing")
            before, result = item["before"], item["result"]
            operation = {"key": item["key"], "state": "prepared"}
            log["operations"].append(operation)
            write_json(output, seal(log, "rollback_sha256"))
            path = f"/zones/{config['zone_id']}/dns_records"
            if item["operation"] == "create":
                api.request("DELETE", path + "/" + checked_id(result["id"], "record_id"))
                expected_records = [row for row in expected_records if row["id"] != result["id"]]
            elif item["operation"] == "update":
                restored = api.request("PATCH", path + "/" + checked_id(result["id"], "record_id"), record_payload(before))["result"]
                expected_records = [restored if row["id"] == result["id"] else row for row in expected_records]
            elif item["operation"] == "delete":
                restored = api.request("POST", path, record_payload(before))["result"]
                expected_records.append(restored)
            else:
                raise Refusal("Unknown receipt operation")
            operation["state"] = "confirmed"
            write_json(output, seal(log, "rollback_sha256"))
        if records_hash(api.records(config)) != records_hash(expected_records):
            raise Refusal("Rollback readback mismatch")
        log.update({"state": "succeeded", "completed_at": now()})
    except Exception:
        log.update({"state": "needs_reconciliation", "stopped_at": now()})
        write_json(output, seal(log, "rollback_sha256"))
        raise
    write_json(output, seal(log, "rollback_sha256"))
    return log


def public_verify(*, assigned_nameservers=None, expected_ds=None, check_tls=False) -> dict:
    """Read public DNS through two resolvers and each observed authoritative NS.

    dnspython comes from the application lockfile. AD bits are resolver evidence,
    not a claim that this client independently implements DNSSEC validation.
    """
    try:
        import dns.flags
        import dns.message
        import dns.query
        import dns.rcode
        import dns.resolver
    except ImportError:
        raise Refusal("Public DNS verification requires the project's locked dnspython; use uv run") from None
    samples = []
    recursors = ("1.1.1.1", "8.8.8.8")
    authorities = set()
    recursive_ns_sets = []
    recursive_ds_sets = []
    resolver_validation = []

    def query(server, address, kind, recursive):
        request = dns.message.make_query(APEX, kind, want_dnssec=True)
        if not recursive:
            request.flags &= ~dns.flags.RD
        try:
            response = dns.query.udp(request, address, timeout=5)
            if response.flags & dns.flags.TC:
                response = dns.query.tcp(request, address, timeout=5)
            requested = [item.to_text() for rrset in response.answer if rrset.rdtype == request.question[0].rdtype for item in rrset]
            record = {"server": server, "address": address, "type": kind, "scope": "recursive" if recursive else "authoritative",
                      "rcode": dns.rcode.to_text(response.rcode()), "authenticated_data": bool(response.flags & dns.flags.AD),
                      "authoritative_answer": bool(response.flags & dns.flags.AA), "requested_answers": requested,
                      "answer": [rrset.to_text() for rrset in response.answer], "authority": [rrset.to_text() for rrset in response.authority],
                      "state": "answers_observed" if requested else "no_requested_type_answer_observed"}
        except Exception as exc:
            record = {"server": server, "type": kind, "scope": "recursive" if recursive else "authoritative", "state": "query_failed", "error_type": type(exc).__name__, "requested_answers": []}
        samples.append(record)
        return record

    for recursor in recursors:
        ns = query(recursor, recursor, "NS", True)
        names = {value.lower().rstrip(".") for value in ns["requested_answers"]}
        authorities.update(names)
        recursive_ns_sets.append(names)
        for kind in ("SOA", "A", "AAAA", "MX", "TXT", "CAA", "DS"):
            answer = query(recursor, recursor, kind, True)
            if kind == "DS":
                recursive_ds_sets.append(set(answer["requested_answers"]))
            if kind == "A":
                resolver_validation.append(bool(answer.get("authenticated_data") and answer["requested_answers"]))
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = list(recursors)
    resolver.timeout, resolver.lifetime = 3, 5
    authority_checks = []
    for server in sorted(authorities):
        try:
            addresses = resolver.resolve(server, "A")
            address = addresses[0].to_text()
            authority_ns = query(server, address, "NS", False)
            authority_checks.append(bool(authority_ns.get("authoritative_answer") and authority_ns["requested_answers"]))
            for kind in ("SOA", "A", "AAAA", "MX", "TXT", "CAA"):
                query(server, address, kind, False)
        except Exception as exc:
            samples.append({"server": server, "scope": "authoritative", "state": "query_failed", "error_type": type(exc).__name__})
            authority_checks.append(False)
    expected = {value.lower().rstrip(".") for value in (assigned_nameservers or [])}
    ns_match = bool(expected and all(observed == expected for observed in recursive_ns_sets) and authority_checks and all(authority_checks))
    ds_match = bool(expected_ds and all(expected_ds in values for values in recursive_ds_sets) and all(resolver_validation))
    result = {"observed_at": now(), "apex": APEX, "scope": "public_dns_sample_not_complete_zone_export", "queries": samples,
              "observed_authoritative_nameservers": sorted(authorities),
              "delegation_matches_assigned_cloudflare": "success" if ns_match else "failed" if expected else "unverified",
              "dnssec_chain_verified": "resolver_ad_and_ds_match" if ds_match else "unverified",
              "dnssec_method": "two_recursive_resolver_AD_flags_plus_exact_provider_DS_comparison; not independent_validation",
              "complete_zone_export": False}
    if check_tls:
        tls_checks = []
        for host in (APEX, "www." + APEX, "app." + APEX, "admin." + APEX):
            try:
                with socket.create_connection((host, 443), timeout=5) as plain:
                    with ssl.create_default_context().wrap_socket(plain, server_hostname=host) as connection:
                        certificate = connection.getpeercert()
                        tls_checks.append({"host": host, "status": "success", "protocol": connection.version(), "expires": certificate.get("notAfter")})
            except (OSError, ssl.SSLError):
                tls_checks.append({"host": host, "status": "failed"})
        result["public_tls"] = tls_checks
        result["origin_tls_verified"] = "unverified; public TLS may terminate at an edge"
    return result


def verify_zone(api, config: dict, *, include_public=False, check_tls=False) -> dict:
    zone = api.zone(config)
    records = api.records(config)
    checks = []
    for item in config.get("managed_records", []):
        owned = [row for row in records if MANAGED_PREFIX + item["key"] in ownership_markers(row)]
        if item.get("state", "present") == "absent":
            matches = not owned
        else:
            payload = desired_payload(item, owned[0] if len(owned) == 1 else None)
            matches = len(owned) == 1 and all(owned[0].get(key) == value for key, value in payload.items())
        checks.append({"key": item["key"], "status": "success" if matches else "failed"})
    optional = {}
    for key, suffix in (("dnssec_api", "dnssec"), ("tls_mode_api", "settings/ssl")):
        try:
            optional[key] = {"status": "observed", "value": api.request("GET", f"/zones/{config['zone_id']}/{suffix}")["result"]}
        except Refusal as exc:
            optional[key] = {"status": "unverified", "reason": str(exc)}
    result = {"observed_at": now(), "apex": APEX, "account_id": config["account_id"], "zone_id": config["zone_id"],
            "zone_active": "success" if zone.get("status") == "active" else "pending_action",
            "assigned_nameservers": zone.get("name_servers", []), "managed_dns": checks,
            "dns_match": "success" if checks and all(row["status"] == "success" for row in checks) else "failed",
            **optional, "godaddy_ns_updated": "unverified", "dnssec_chain_verified": "unverified",
            "origin_tls_verified": "unverified", "application_deployed": "unverified",
            "mail_roundtrip_verified": "unverified", "payment_verified": "unverified",
            "note": "API readback is not delegation, DNSSEC chain, TLS, deployment, mail, or payment proof."}
    if include_public:
        result["public_checks"] = public_verify(assigned_nameservers=zone.get("name_servers", []),
                                                expected_ds=optional.get("dnssec_api", {}).get("value", {}).get("ds"), check_tls=check_tls)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Read scoped zone and BIND export; missing zone ID produces discovery evidence only")
    inspect.add_argument("--config", required=True)
    inspect.add_argument("--out", required=True)
    plan = sub.add_parser("plan", help="Produce a deterministic managed-record diff; no network writes")
    plan.add_argument("--config", required=True)
    plan.add_argument("--snapshot", required=True)
    plan.add_argument("--authority-proof", required=True)
    plan.add_argument("--out", required=True)
    apply = sub.add_parser("apply", help="Apply a reviewed unexpired plan after fresh immutable target readback")
    apply.add_argument("--plan", required=True)
    apply.add_argument("--approve-plan-sha256", required=True)
    apply.add_argument("--receipt", required=True)
    verify = sub.add_parser("verify", help="Read actual zone/DNS/settings; other activation evidence stays separate")
    verify.add_argument("--config")
    verify.add_argument("--out", required=True)
    verify.add_argument("--public-only", action="store_true", help="Read public DNS without a Cloudflare token; does not prove account or cutover")
    verify.add_argument("--include-public", action="store_true")
    verify.add_argument("--tls", action="store_true", help="Also check public TLS certificates; this does not verify origin TLS")
    undo = sub.add_parser("rollback", help="Revert only unchanged managed records from a confirmed receipt")
    undo.add_argument("--receipt", required=True)
    undo.add_argument("--approve-receipt-sha256", required=True)
    undo.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            result = build_plan(read_json(args.config), read_json(args.snapshot), read_json(args.authority_proof))
            write_json(Path(args.out), result, exclusive=True)
            print(json.dumps({"status": "planned", "operations": len(result["actions"]), "plan_sha256": result["plan_sha256"], "expires_at": result["expires_at"]}))
            return 0
        if args.command == "verify" and args.public_only:
            result = public_verify(check_tls=args.tls)
            write_json(Path(args.out), result, exclusive=True)
            print(json.dumps({"status": "observed", "observed_authoritative_nameservers": result["observed_authoritative_nameservers"], "complete_zone_export": False}))
            return 0
        if args.command == "verify" and not args.config:
            raise Refusal("--config is required except for --public-only")
        api = CloudflareAPI(os.environ.get("CLOUDFLARE_API_TOKEN", ""))
        if args.command == "inspect":
            result = inspect_zone(api, read_json(args.config), Path(args.out))
        elif args.command == "apply":
            result = apply_plan(api, read_json(args.plan), args.approve_plan_sha256, Path(args.receipt))
        elif args.command == "rollback":
            result = rollback(api, read_json(args.receipt), args.approve_receipt_sha256, Path(args.out))
        else:
            result = verify_zone(api, read_json(args.config), include_public=args.include_public, check_tls=args.tls)
            write_json(Path(args.out), result, exclusive=True)
        print(json.dumps({key: result[key] for key in ("state", "snapshot_sha256", "receipt_sha256", "rollback_sha256", "zone_active", "dns_match") if key in result}))
        return 0
    except (Refusal, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
