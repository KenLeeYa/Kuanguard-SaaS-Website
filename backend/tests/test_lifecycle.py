from datetime import timedelta
import json
from pathlib import Path
from uuid import uuid4
import zipfile

import pytest

from kuanguard import models as m
from kuanguard.db import add, all_rows, change, one
from kuanguard.lifecycle import canonical, erasure_manifest, execute_erasure, export_archive, object_inventory
from kuanguard.security import digest
from kuanguard.seed import fixed


def post(client, path, payload, key=None):
    return client.post(path, json=payload, headers={"idempotency-key": key or str(uuid4())})


def prepare_offboard(customer, owner):
    request = post(customer, "/customer/lifecycle/requests", {"kind": "tenant_offboard", "reason": "合成退場驗證，不含真實客戶"})
    assert request.status_code == 200, request.text
    plan = post(owner, "/internal/lifecycle/plan", {"request_id": request.json()["id"]})
    assert plan.status_code == 200, plan.text
    return request.json(), plan.json()


def test_offboard_requires_customer_request_and_both_roles(platform):
    customer, owner, pm, b = (platform["login"](profile) for profile in ("customer-a", "owner-a", "pm-a", "customer-b"))
    request, plan = prepare_offboard(customer, owner)
    assert pm.get("/internal/lifecycle").status_code == 403
    assert post(pm, "/internal/lifecycle/plan", {"request_id": request["id"]}).status_code == 403
    assert b.get("/customer/lifecycle/requests").json()["items"] == []
    payload = {"plan_id": plan["id"], "expected_digest": plan["digest"], "confirmation": "REVOKE_CUSTOMER_ACCESS_KEEP_DATA"}
    assert post(customer, "/internal/lifecycle/offboard", payload).status_code == 403
    assert post(owner, "/internal/lifecycle/offboard", {**payload, "expected_digest": "0"*64}).status_code == 409
    with platform["engine"].begin() as conn:
        add(conn, m.jobs, tenant_id=fixed("tenant-a"), kind="report", resource_id=str(uuid4()), status="running", lease_until=m.now()+timedelta(minutes=5))
    assert post(owner, "/internal/lifecycle/offboard", payload).status_code == 409


def test_offboard_releases_unstarted_restricts_access_keeps_data_and_other_tenant(platform):
    customer, owner, learner, b = (platform["login"](profile) for profile in ("customer-a", "owner-a", "learner-a", "customer-b"))
    enrollment = post(customer, "/customer/training/enrollments", {"course_id": fixed("course"), "learner_id": fixed("learner-a"), "cohort": "offboard-test"})
    assert enrollment.status_code == 200, enrollment.text
    with platform["engine"].begin() as conn:
        prior_ledger = len(all_rows(conn, m.wallet_transactions, fixed("tenant-a")))
        prior_projects = len(all_rows(conn, m.projects, fixed("tenant-a")))
    request, plan = prepare_offboard(customer, owner)
    payload = {"plan_id": plan["id"], "expected_digest": plan["digest"], "confirmation": "REVOKE_CUSTOMER_ACCESS_KEEP_DATA"}
    key = str(uuid4())
    response = post(owner, "/internal/lifecycle/offboard", payload, key)
    assert response.status_code == 200, response.text
    assert response.json()["data_erased"] is False
    assert post(owner, "/internal/lifecycle/offboard", payload, key).json() == response.json()
    assert customer.get("/customer/dashboard").status_code == 401
    assert learner.get("/learner/enrollments").status_code == 401
    assert b.get("/customer/dashboard").status_code == 200
    assert owner.get("/internal/lifecycle").status_code == 200
    assert post(owner, "/internal/training/entitlements", {}).status_code == 401
    with platform["engine"].begin() as conn:
        assert len(all_rows(conn, m.projects, fixed("tenant-a"))) == prior_projects
        assert len(all_rows(conn, m.wallet_transactions, fixed("tenant-a"))) > prior_ledger
        assert one(conn, m.enrollments, fixed("tenant-a"), m.enrollments.c.id == enrollment.json()["id"])["status"] in {"cancelled", "revoked"}
        assert one(conn, m.tenants, None, m.tenants.c.id == fixed("tenant-a"))["status"] == "offboarding"


def test_customer_export_uses_authorized_projections(platform):
    a, learner, b = platform["login"](), platform["login"]("learner-a"), platform["login"]("customer-b")
    assert a.get("/customer/data-export?section=findings").json()["items"] == []
    assert learner.get("/customer/data-export?section=orders").status_code == 403
    assert a.get("/customer/data-export?section=projects&tenant_id=x").status_code == 422
    assert a.get("/customer/data-export?section=imports").status_code == 422
    result = a.get("/customer/data-export?section=projects").json()
    assert {row["id"] for row in result["items"]} == {fixed("project-a")}
    assert {row["id"] for row in b.get("/customer/data-export?section=projects").json()["items"]} == {fixed("project-b")}


@pytest.mark.parametrize("revocation", ["session", "membership", "tenant"])
def test_mutation_rechecks_revocation_after_waiting_for_tenant_lock(platform, monkeypatch, revocation):
    from kuanguard import security
    client = platform["login"]()
    original = security.set_tenant
    def revoke_after_lock(conn, tenant, mutation=False):
        original(conn, tenant, mutation)
        if mutation:
            if revocation == "session":
                conn.execute(m.sessions.update().where(m.sessions.c.tenant_id == tenant).values(revoked=True))
            elif revocation == "membership":
                conn.execute(m.memberships.update().where(m.memberships.c.tenant_id == tenant,
                    m.memberships.c.user_id == fixed("customer-a")).values(active=False))
            else:
                change(conn, m.tenants, None, tenant, status="offboarding")
    monkeypatch.setattr(security, "set_tenant", revoke_after_lock)
    response = post(client, "/customer/wallet/orders", {"points": 100})
    assert response.status_code == 401
    with platform["engine"].begin() as conn:
        assert all_rows(conn, m.orders, fixed("tenant-a")) == []


def test_private_archive_is_tenant_scoped_and_excludes_auth_secrets(platform):
    from kuanguard.config import settings
    platform["login"]()
    storage = settings().local_data_dir
    for tenant, body in ((fixed("tenant-a"), b"a-private-synthetic"), (fixed("tenant-b"), b"b-private-synthetic")):
        path = storage / tenant / "reports" / "example.txt"
        path.parent.mkdir(parents=True)
        path.write_bytes(body)
    destination = platform["tmp"] / "private-export.zip"
    with platform["engine"].begin() as conn:
        manifest = export_archive(conn, fixed("tenant-a"), destination)
    assert len(manifest["objects"]) == 1
    with zipfile.ZipFile(destination) as archive:
        assert "tables/sessions.jsonl" not in archive.namelist()
        assert "tables/form_drafts.jsonl" not in archive.namelist()
        assert all(fixed("tenant-b") not in name for name in archive.namelist())
        for name in archive.namelist():
            assert b"b-private-synthetic" not in archive.read(name)
        assert json.loads(archive.read("manifest.json"))["manifest_sha256"] == manifest["manifest_sha256"]
    with platform["engine"].begin() as conn, pytest.raises(ValueError, match="new private path"):
        export_archive(conn, fixed("tenant-a"), destination)


def test_private_archive_never_contains_active_campaign_bearer_lookup_token(platform):
    from backend.tests.test_platform import make_campaign
    customer = platform["login"]()
    campaign = make_campaign(customer, "accepted")
    destination = platform["tmp"] / "campaign-export.zip"
    with platform["engine"].begin() as conn:
        lookup = one(conn, m.jobs, None, m.jobs.c.kind == "tracking_lookup",
                     m.jobs.c.resource_id == campaign["messages"][0]["id"])
        assert lookup and lookup["status"] == "active"
        token = lookup["id"]
        manifest = export_archive(conn, fixed("tenant-a"), destination)
    assert customer.get(f"/sim/{token}/education").status_code == 200  # Demonstrate that the omitted value is still a live bearer.
    assert {"jobs", "sessions", "idempotency", "portfolio_connectors"}.isdisjoint(manifest["tables"])
    with zipfile.ZipFile(destination) as archive:
        assert all(token.encode() not in archive.read(name) for name in archive.namelist())


def isolated_erasure(platform):
    from kuanguard.config import settings
    tenant = str(uuid4())
    with platform["engine"].begin() as conn:
        add(conn, m.tenants, id=tenant, name="合成可丟棄退場資料", status="offboarding")
        user = add(conn, m.users, name="合成個人", email=f"{tenant}@example.invalid")
        add(conn, m.memberships, tenant_id=tenant, user_id=user["id"], role="learner", active=False)
        add(conn, m.wallets, tenant, frozen=True)
        request = add(conn, m.deletion_requests, tenant, data_class="tenant_offboard", status="erasure_approved", reason="synthetic test only",
                      requested_by=user["id"], backup_expiry=m.now()-timedelta(days=1))
        add(conn, m.retention_policies, tenant, data_class="tenant_all", days=0, version=1, approved=True)
        add(conn, m.notifications, tenant, user_id=user["id"], title="合成個資", text="should erase")
    path = settings().local_data_dir / tenant / "raw" / "test.txt"
    path.parent.mkdir(parents=True)
    path.write_text("synthetic raw", encoding="utf-8")
    with platform["engine"].begin() as conn:
        manifest = erasure_manifest(conn, tenant, request["id"])
    return tenant, user, request, path, manifest


def test_erasure_exact_manifest_scoped_delete_and_idempotent_receipt(platform):
    tenant, user, _, path, manifest = isolated_erasure(platform)
    with pytest.raises(ValueError, match="Exact reviewed"):
        execute_erasure(platform["engine"], manifest, "0"*64)
    result = execute_erasure(platform["engine"], manifest, digest(canonical(manifest)))
    assert result["status"] == "erased" and not path.exists()
    assert execute_erasure(platform["engine"], manifest, digest(canonical(manifest))) == result
    with platform["engine"].begin() as conn:
        assert all_rows(conn, m.notifications, tenant) == []
        assert all_rows(conn, m.memberships, None, m.memberships.c.tenant_id == tenant) == []
        assert one(conn, m.users, None, m.users.c.id == user["id"])["name"] == "已匿名化"
        assert one(conn, m.tenants, None, m.tenants.c.id == fixed("tenant-a"))["status"] == "active"


def test_erasure_blocks_changed_source_future_backup_and_live_identity_is_preserved(platform):
    tenant, user, request, path, manifest = isolated_erasure(platform)
    with platform["engine"].begin() as conn:
        change(conn, m.deletion_requests, tenant, request["id"], backup_expiry=m.now()+timedelta(days=1))
        with pytest.raises(ValueError, match="expiry"):
            erasure_manifest(conn, tenant, request["id"])
    assert path.exists()
    with pytest.raises(ValueError):
        execute_erasure(platform["engine"], manifest, digest(canonical(manifest)))
    with platform["engine"].begin() as conn:
        change(conn, m.deletion_requests, tenant, request["id"], backup_expiry=m.now()-timedelta(days=1))
        add(conn, m.memberships, tenant_id=fixed("tenant-b"), user_id=user["id"], role="learner", active=True)
        refreshed = erasure_manifest(conn, tenant, request["id"])
    execute_erasure(platform["engine"], refreshed, digest(canonical(refreshed)))
    with platform["engine"].begin() as conn:
        assert one(conn, m.users, None, m.users.c.id == user["id"])["name"] == "合成個人"


def test_erasure_resume_after_object_failure_uses_receipt_without_redeleting_db(platform, monkeypatch):
    tenant, _, _, path, manifest = isolated_erasure(platform)
    original = Path.unlink
    def fail_once(target, *args, **kwargs):
        if target == path:
            raise OSError("synthetic interrupted cleanup")
        return original(target, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", fail_once)
    with pytest.raises(OSError, match="interrupted"):
        execute_erasure(platform["engine"], manifest, digest(canonical(manifest)))
    with platform["engine"].begin() as conn:
        assert one(conn, m.tenants, None, m.tenants.c.id == tenant)["status"] == "erasing"
    monkeypatch.setattr(Path, "unlink", original)
    assert execute_erasure(platform["engine"], manifest, digest(canonical(manifest)))["status"] == "erased"
    assert object_inventory(tenant) == []
