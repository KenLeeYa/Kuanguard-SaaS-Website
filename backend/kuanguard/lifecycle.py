"""Consent-bound tenant offboarding; erasure is a separate privileged retention operation."""
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from uuid import UUID
import zipfile

from fastapi.encoders import jsonable_encoder
from sqlalchemy import MetaData, select, text

from . import models as m, partner_models as p, wallet
from .config import settings
from .db import add, all_rows, aware, change, one, set_tenant
from .security import digest, fail


def canonical(value):
    return json.dumps(jsonable_encoder(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def tenant_tables(conn):
    metadata = MetaData()
    metadata.reflect(conn)
    # Reflect the dedicated database to cover additive modules and enforce actual FK order.
    return [table for table in metadata.sorted_tables if "tenant_id" in table.c]


def auth_sidecars(conn, tenant_id):
    sessions = select(m.sessions.c.id).where(m.sessions.c.tenant_id == tenant_id)
    intents = select(p.portal_login_intents.c.id).where(p.portal_login_intents.c.tenant_id == tenant_id)
    links = all_rows(conn, p.portal_oidc_links, None, p.portal_oidc_links.c.intent_id.in_(intents))
    return {"session_contexts": all_rows(conn, p.session_contexts, None, p.session_contexts.c.session_id.in_(sessions)),
            "portal_oidc_links": links,
            "oidc_states": all_rows(conn, m.oidc_states, None, m.oidc_states.c.id.in_([row["oidc_state_id"] for row in links]))}


def object_inventory(tenant_id):
    if str(UUID(tenant_id)) != tenant_id:
        raise ValueError("Canonical tenant UUID required")
    base = settings().local_data_dir.resolve()
    root = base / tenant_id
    if root.is_symlink() or (hasattr(root, "is_junction") and root.is_junction()) or not root.resolve().is_relative_to(base):
        raise ValueError("Unsafe tenant storage root")
    result = []
    if root.exists():
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise ValueError("Linked storage is not allowed")
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("Object escapes tenant storage")
            if path.is_file():
                with path.open("rb") as source:
                    sha256 = hashlib.file_digest(source, "sha256").hexdigest()
                result.append({"path": path.relative_to(base).as_posix(), "bytes": path.stat().st_size,
                               "sha256": sha256})
    return result


def offboard_manifest(conn, tenant_id):
    jobs = all_rows(conn, m.jobs, None, m.jobs.c.tenant_id == tenant_id,
                    m.jobs.c.kind.in_(["report", "sandbox_mail"]), m.jobs.c.status == "running")
    unknown = all_rows(conn, m.message_plans, tenant_id, m.message_plans.c.status.in_(["unknown", "in_flight"]))
    rows = {}
    for table in (m.memberships, m.campaigns, m.message_plans, m.enrollments, m.reservations, m.jobs, m.batches):
        rows[table.name] = [dict(row) for row in conn.execute(select(table).where(table.c.tenant_id == tenant_id).order_by(table.c.id)).mappings()]
    return {"tenant_id": tenant_id, "operation": "offboard-v1", "state_hash": digest(canonical(rows)),
            "blocking_running_jobs": [row["id"] for row in jobs],
            "blocking_unknown_messages": [row["id"] for row in unknown],
            "unstarted_enrollments": sum(row["status"] == "assigned" for row in rows["enrollments"]),
            "planned_messages": sum(row["status"] == "planned" for row in rows["message_plans"]),
            "policy": "revoke customer access; keep reports, ledger, certificates and settlement history"}


def offboard(ctx, plan):
    from .learning_entitlements import release_unstarted_for_learner
    from .entitlements import finish
    current = offboard_manifest(ctx.conn, ctx.tenant_id)
    if current != plan["manifest"] or aware(plan["expires_at"]) <= m.now():
        fail(409, "LIFECYCLE_PLAN_CHANGED", "資料狀態已變動，請重新預覽退場差異。")
    if current["blocking_running_jobs"] or current["blocking_unknown_messages"]:
        fail(409, "OFFBOARD_RECONCILIATION_REQUIRED", "先等待工作完成並核對未知寄送，才能執行退場。")
    for message in all_rows(ctx.conn, m.message_plans, ctx.tenant_id, m.message_plans.c.status == "planned"):
        wallet.release(ctx.conn, ctx.tenant_id, message["reservation_id"], "tenant offboarding: confirmed unsent")
        change(ctx.conn, m.message_plans, ctx.tenant_id, message["id"], status="cancelled")
    memberships = all_rows(ctx.conn, m.memberships, None, m.memberships.c.tenant_id == ctx.tenant_id)
    for user_id in {row["user_id"] for row in memberships}:
        release_unstarted_for_learner(ctx.conn, ctx.tenant_id, user_id, "tenant offboarding: unstarted authorization")
    for batch in all_rows(ctx.conn, m.batches, ctx.tenant_id, m.batches.c.status.notin_(["delivered", "accepted", "cancelled"])):
        consumed = one(ctx.conn, m.entitlement_ledger, ctx.tenant_id,
                       m.entitlement_ledger.c.batch_id == batch["id"], m.entitlement_ledger.c.kind == "consume")
        if not consumed:
            finish(ctx.conn, ctx.tenant_id, batch, "release", "tenant offboarding")
        change(ctx.conn, m.batches, ctx.tenant_id, batch["id"], status="cancelled", version=batch["version"] + 1)
    ctx.conn.execute(m.resource_slots.delete().where(m.resource_slots.c.tenant_id == ctx.tenant_id))
    ctx.conn.execute(m.campaigns.update().where(m.campaigns.c.tenant_id == ctx.tenant_id).values(status="cancelled"))
    ctx.conn.execute(m.jobs.update().where(m.jobs.c.tenant_id == ctx.tenant_id,
        m.jobs.c.kind.in_(["report", "sandbox_mail", "tracking_lookup"]),
        m.jobs.c.status.in_(["queued", "paused", "active"])).values(status="cancelled", claim_token=None, lease_until=None))
    customer_roles = {"customer_admin", "customer_contact", "campaign_manager", "training_manager", "billing_manager", "learner"}
    ctx.conn.execute(m.memberships.update().where(m.memberships.c.tenant_id == ctx.tenant_id,
        m.memberships.c.role.in_(customer_roles)).values(active=False))
    employee_ids = {row["user_id"] for row in memberships if row["active"] and row["role"] not in customer_roles}
    ctx.conn.execute(m.sessions.update().where(m.sessions.c.tenant_id == ctx.tenant_id,
        m.sessions.c.user_id.notin_(employee_ids)).values(revoked=True))
    ctx.conn.execute(m.form_drafts.delete().where(m.form_drafts.c.tenant_id == ctx.tenant_id))
    ctx.conn.execute(m.wallets.update().where(m.wallets.c.tenant_id == ctx.tenant_id).values(frozen=True))
    change(ctx.conn, m.tenants, None, ctx.tenant_id, status="offboarding")
    change(ctx.conn, m.deletion_requests, ctx.tenant_id, plan["request_id"], status="offboarded")
    ctx.audit("tenant.offboard", plan["id"], f"plan={plan['digest']}; ledger and objects retained")
    return {"status": "offboarding", "data_erased": False, "plan_digest": plan["digest"],
            "remaining": "financial settlement, approved retention and backup expiry before separate erasure"}


def erasure_manifest(conn, tenant_id, request_id):
    tenant = one(conn, m.tenants, None, m.tenants.c.id == tenant_id)
    request = one(conn, m.deletion_requests, tenant_id, m.deletion_requests.c.id == request_id)
    policy = one(conn, m.retention_policies, tenant_id, m.retention_policies.c.data_class == "tenant_all",
                 m.retention_policies.c.approved.is_(True))
    if not tenant or tenant["status"] != "offboarding" or not request or request["status"] != "erasure_approved" or not policy:
        raise ValueError("Approved offboarding request and tenant_all retention policy required")
    if (not request["backup_expiry"] or aware(request["backup_expiry"]) > m.now()
            or aware(request["created_at"]) + timedelta(days=policy["days"]) > m.now()):
        raise ValueError("Retention or attested backup expiry has not elapsed")
    if one(conn, m.jobs, None, m.jobs.c.tenant_id == tenant_id, m.jobs.c.status == "running"):
        raise ValueError("Running work blocks erasure")
    if one(conn, m.message_plans, tenant_id, m.message_plans.c.status.in_(["unknown", "in_flight"])):
        raise ValueError("Unknown delivery outcome blocks erasure")
    if one(conn, m.reservations, tenant_id, m.reservations.c.status == "reserved"):
        raise ValueError("Unsettled reservations block erasure")
    if any(wallet.balances(conn, tenant_id, lot["id"])["available"] > 0
           for lot in all_rows(conn, m.point_lots, tenant_id, m.point_lots.c.expires_at > m.now())):
        raise ValueError("Unsettled wallet points block erasure")
    if one(conn, m.orders, tenant_id, m.orders.c.status == "pending") or one(
            conn, m.refunds, tenant_id, m.refunds.c.status.in_(["manual_review", "pending"])):
        raise ValueError("Pending payment/refund settlement blocks erasure")
    tables = {}
    for table in tenant_tables(conn):
        rows = [dict(row) for row in conn.execute(select(table).where(table.c.tenant_id == tenant_id).order_by(table.c.id)).mappings()]
        tables[table.name] = {"rows": len(rows), "sha256": digest(canonical(rows))}
    sidecars = {name: {"rows": len(rows), "sha256": digest(canonical(sorted(rows, key=lambda row: row["id"])))}
                for name, rows in auth_sidecars(conn, tenant_id).items()}
    return {"tenant_id": tenant_id, "request_id": request_id, "operation": "erase-v1", "tables": tables, "auth_sidecars": sidecars,
            "objects": object_inventory(tenant_id), "policy_version": policy["version"],
            "backup_expiry": aware(request["backup_expiry"]).isoformat(), "retained": ["anonymous receipt", "global presales inquiries under separate policy"]}


def export_archive(conn, tenant_id, destination: Path):
    """Privileged offline archive. Authentication secrets are never exported."""
    destination = destination.resolve()
    storage = settings().local_data_dir.resolve()
    if destination.exists() or destination.is_relative_to(storage):
        raise ValueError("Export requires a new private path outside the object store")
    files = object_inventory(tenant_id)
    excluded = {"sessions", "oidc_states", "form_drafts", "jobs", "idempotency", "portfolio_connectors", "portal_login_intents"}
    tables = [table for table in tenant_tables(conn) if table.name not in excluded]
    manifest = {"tenant_id": tenant_id, "created_at": m.now().isoformat(), "tables": {}, "objects": files,
                "excluded": sorted(excluded), "format": "kuanguard-private-export-v1"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("tenant.json", canonical(one(conn, m.tenants, None, m.tenants.c.id == tenant_id)))
        user_ids = {row["user_id"] for row in all_rows(conn, m.memberships, None, m.memberships.c.tenant_id == tenant_id)}
        profiles = [{key: row[key] for key in ("id", "name", "email")} for row in
                    all_rows(conn, m.users, None, m.users.c.id.in_(user_ids))]
        archive.writestr("user-profiles.json", canonical(profiles))
        for table in tables:
            content = b""
            count = 0
            # Stream the DB cursor; the zip member is written without loading the entire tenant.
            hasher = hashlib.sha256()
            with archive.open(f"tables/{table.name}.jsonl", "w") as output:
                for row in conn.execute(select(table).where(table.c.tenant_id == tenant_id).order_by(table.c.id)
                                        .execution_options(stream_results=True)).mappings():
                    record = dict(row)
                    for field in ("tracking_hash", "verification_hash", "token_hash"):
                        record.pop(field, None)
                    content = canonical(record) + b"\n"
                    output.write(content)
                    hasher.update(content)
                    count += 1
            manifest["tables"][table.name] = {"rows": count, "sha256": hasher.hexdigest()}
        for item in files:
            path = storage / item["path"]
            hasher = hashlib.sha256()
            with path.open("rb") as source, archive.open("objects/" + item["path"], "w") as output:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(block)
                    hasher.update(block)
            if hasher.hexdigest() != item["sha256"]:
                raise ValueError("Source object changed during export; archive is incomplete")
        manifest["manifest_sha256"] = digest(canonical(manifest))
        archive.writestr("manifest.json", canonical(manifest))
    return manifest


def execute_erasure(db, manifest, confirmed_digest):
    """Administrative CLI only; idempotent DB tombstone followed by verified object cleanup."""
    plan_digest = digest(canonical(manifest))
    if plan_digest != confirmed_digest:
        raise ValueError("Exact reviewed plan digest required")
    tenant = manifest["tenant_id"]
    with db.begin() as conn:
        set_tenant(conn, tenant, mutation=True)
        receipt = one(conn, m.erasure_receipts, None, m.erasure_receipts.c.plan_digest == plan_digest)
        if not receipt:
            if erasure_manifest(conn, tenant, manifest["request_id"]) != manifest:
                raise ValueError("Erasure source changed; generate a new plan")
            user_ids = {row["user_id"] for row in all_rows(conn, m.memberships, None, m.memberships.c.tenant_id == tenant)}
            order_ids = [row["id"] for row in all_rows(conn, m.orders, tenant)]
            sidecars = auth_sidecars(conn, tenant)
            for table in (p.session_contexts, p.portal_oidc_links, m.oidc_states):
                conn.execute(table.delete().where(table.c.id.in_([row["id"] for row in sidecars[table.name]])))
            tables = tenant_tables(conn)
            for table in reversed(tables):
                # Only the reviewed immutable triggers on this table are disabled, inside this transaction.
                if conn.dialect.name == "postgresql":
                    triggers = conn.execute(text("SELECT tgname FROM pg_trigger WHERE tgrelid=to_regclass(:name) AND NOT tgisinternal AND tgname='immutable_record'"), {"name": table.name}).scalars().all()
                    if triggers:
                        conn.exec_driver_sql(f'ALTER TABLE "{table.name}" DISABLE TRIGGER immutable_record')
                conn.execute(table.delete().where(table.c.tenant_id == tenant))
                if conn.dialect.name == "postgresql" and triggers:
                    conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ENABLE TRIGGER immutable_record')
            conn.execute(m.inbox.delete().where(m.inbox.c.order_id.in_(order_ids)))
            for user_id in user_ids:
                conn.execute(select(m.users.c.id).where(m.users.c.id == user_id).with_for_update())
                if not one(conn, m.memberships, None, m.memberships.c.user_id == user_id):
                    change(conn, m.users, None, user_id, name="已匿名化", email=f"deleted-{user_id}@example.invalid", oidc_subject=None, active=False)
            change(conn, m.tenants, None, tenant, name="已刪除企業", status="erasing", verified=False)
            receipt = add(conn, m.erasure_receipts, tenant_ref=tenant, plan_digest=plan_digest, manifest=manifest, status="objects_pending")
        elif receipt["manifest"] != manifest:
            raise ValueError("Receipt manifest mismatch")
    expected = {item["path"]: item for item in manifest["objects"]}
    remaining = object_inventory(tenant)
    if any(expected.get(item["path"]) != item for item in remaining):
        raise ValueError("Unexpected or changed object; cleanup paused without deleting it")
    base = settings().local_data_dir.resolve()
    for item in remaining:
        path = base / item["path"]
        if not path.resolve().is_relative_to(base / tenant):
            raise ValueError("Unsafe cleanup path")
        path.unlink()  # Only exact files in the reviewed tenant manifest, never a recursive delete.
    if receipt["status"] != "erased":
        with db.begin() as conn:
            set_tenant(conn, tenant, mutation=True)
            change(conn, m.erasure_receipts, None, receipt["id"], status="erased", completed_at=m.now())
            change(conn, m.tenants, None, tenant, status="erased")
    return {"status": "erased", "plan_digest": plan_digest, "objects_deleted": len(manifest["objects"])}
