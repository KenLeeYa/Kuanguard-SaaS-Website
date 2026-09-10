"""Finite course seats, separate from points; use a serialized tenant transaction."""
from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Integer,
    MetaData, String, Table, Text, UniqueConstraint, or_, select,
)

from . import models as m, wallet
from .db import add, all_rows, aware, change, one, set_tenant
from .security import fail

POLICY = "training-seat-2026-09-v1"
training_metadata = MetaData(naming_convention=m.metadata.naming_convention)
entitlements = Table(
    "training_entitlements", training_metadata,
    Column("id", String(36), primary_key=True, default=m.uid),
    Column("created_at", DateTime(timezone=True), nullable=False, default=m.now),
    Column("tenant_id", String(36), ForeignKey(m.tenants.c.id), nullable=False, index=True),
    Column("course_id", String(36), ForeignKey(m.courses.c.id), nullable=False),
    Column("cohort", String(80)),
    Column("source", String(30), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("starts_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("contract_id", String(36)),
    Column("source_reference", String(200), nullable=False),
    Column("reason", Text, nullable=False),
    Column("granted_by", String(36), ForeignKey(m.users.c.id), nullable=False),
    UniqueConstraint("tenant_id", "id"),
    ForeignKeyConstraint(["tenant_id", "contract_id"], [m.contracts.c.tenant_id, m.contracts.c.id]),
    CheckConstraint("quantity > 0 AND quantity <= 100000", name="training_seat_quantity"),
    CheckConstraint("expires_at > starts_at", name="training_seat_period"),
    CheckConstraint("source IN ('annual_included', 'gift', 'manual')", name="training_seat_source"),
    CheckConstraint("source <> 'annual_included' OR contract_id IS NOT NULL", name="annual_contract"),
)
ledger = Table(
    "training_entitlement_ledger", training_metadata,
    Column("id", String(36), primary_key=True, default=m.uid),
    Column("created_at", DateTime(timezone=True), nullable=False, default=m.now),
    Column("tenant_id", String(36), ForeignKey(m.tenants.c.id), nullable=False, index=True),
    Column("entitlement_id", String(36), nullable=False),
    Column("enrollment_id", String(36), nullable=False),
    Column("kind", String(12), nullable=False),
    Column("quantity", Integer, nullable=False, default=1),
    Column("reason", Text, nullable=False),
    UniqueConstraint("tenant_id", "id"),
    UniqueConstraint("tenant_id", "enrollment_id", "kind"),
    ForeignKeyConstraint(["tenant_id", "entitlement_id"], [entitlements.c.tenant_id, entitlements.c.id]),
    ForeignKeyConstraint(["tenant_id", "enrollment_id"], [m.enrollments.c.tenant_id, m.enrollments.c.id]),
    CheckConstraint("quantity = 1", name="training_seat_single"),
    CheckConstraint("kind IN ('reserve', 'consume', 'release')", name="training_seat_kind"),
)
TRAINING_TABLES = (entitlements, ledger)
for training_table in TRAINING_TABLES:
    if training_table.name not in m.TENANT_TABLES:
        m.TENANT_TABLES.append(training_table.name)


def balances(conn, tenant, entitlement):
    totals = {kind: 0 for kind in ("reserve", "consume", "release")}
    for row in all_rows(conn, ledger, tenant, ledger.c.entitlement_id == entitlement["id"]):
        totals[row["kind"]] += row["quantity"]
    reserved = totals["reserve"]-totals["consume"]-totals["release"]
    available = entitlement["quantity"]-reserved-totals["consume"]
    status = "expired" if aware(entitlement["expires_at"]) <= m.now() else (
        "scheduled" if aware(entitlement["starts_at"]) > m.now() else "active")
    return {"reserved": reserved, "consumed": totals["consume"], "released": totals["release"],
            "available": available if status == "active" else 0, "status": status}


def entitlement_view(conn, tenant, row):
    course = one(conn, m.courses, None, m.courses.c.id == row["course_id"])
    return {**row, **balances(conn, tenant, row), "course_title": course["title"],
            "unit": "enrollment_seat", "policy_version": POLICY}


def eligible_entitlement(conn, tenant, course_id, cohort, *, lock=True):
    # Grants remain immutable, so use the tenant lock without requiring UPDATE permission on them.
    if lock:
        set_tenant(conn, tenant, mutation=True)
    query = select(entitlements).where(
        entitlements.c.tenant_id == tenant, entitlements.c.course_id == course_id,
        or_(entitlements.c.cohort.is_(None), entitlements.c.cohort == cohort),
        entitlements.c.starts_at <= m.now(), entitlements.c.expires_at > m.now(),
    ).order_by(entitlements.c.expires_at, entitlements.c.created_at, entitlements.c.id)
    candidates = conn.execute(query).mappings()
    for item in candidates:
        row = dict(item)
        if balances(conn, tenant, row)["available"] > 0:
            return row
    return None


def reserve_seat(conn, tenant, enrollment, entitlement):
    set_tenant(conn, tenant, mutation=True)
    entitlement = one(conn, entitlements, tenant, entitlements.c.id == entitlement["id"])
    if not entitlement:
        fail(404, "TRAINING_AUTHORIZATION_MISSING", "找不到可存取的課程席次。")
    if enrollment["reservation_id"] is not None:
        fail(409, "AUTHORIZATION_CONFLICT", "同一課程授權不能同時預留席次與點數。")
    if (enrollment["course_id"] != entitlement["course_id"]
            or entitlement["cohort"] not in {None, enrollment["cohort"]}
            or aware(enrollment["expires_at"]) > aware(entitlement["expires_at"])):
        fail(409, "AUTHORIZATION_CONFLICT", "課程、期別或效期不符合席次授權。")
    prior = one(conn, ledger, tenant, ledger.c.enrollment_id == enrollment["id"], ledger.c.kind == "reserve")
    if prior:
        if prior["entitlement_id"] != entitlement["id"]:
            fail(409, "AUTHORIZATION_CONFLICT", "此課程已有不同的席次來源。")
        return prior
    if balances(conn, tenant, entitlement)["available"] < 1:
        fail(409, "TRAINING_SEATS_EXHAUSTED", "適用席次已用完或已到期。")
    return add(conn, ledger, tenant, entitlement_id=entitlement["id"], enrollment_id=enrollment["id"],
               kind="reserve", quantity=1, reason="course assigned")


def finish_seat(conn, tenant, enrollment_id, kind, reason):
    set_tenant(conn, tenant, mutation=True)
    held = one(conn, ledger, tenant, ledger.c.enrollment_id == enrollment_id, ledger.c.kind == "reserve")
    if not held:
        fail(409, "TRAINING_AUTHORIZATION_MISSING", "找不到有效的課程席次預留。")
    terminal = one(conn, ledger, tenant, ledger.c.enrollment_id == enrollment_id,
                   ledger.c.kind.in_(["consume", "release"]))
    if terminal:
        if terminal["kind"] != kind:
            fail(409, "TRAINING_AUTHORIZATION_SETTLED", "課程席次已結算，不能重複耗用或釋放。")
        return terminal
    entitlement = one(conn, entitlements, tenant, entitlements.c.id == held["entitlement_id"])
    if kind == "consume" and not aware(entitlement["starts_at"]) <= m.now() < aware(entitlement["expires_at"]):
        fail(410, "COURSE_EXPIRED", "課程席次授權已到期。")
    return add(conn, ledger, tenant, entitlement_id=entitlement["id"], enrollment_id=enrollment_id,
               kind=kind, quantity=1, reason=reason)


def consume_authorization(conn, tenant, enrollment):
    if enrollment["reservation_id"]:
        return wallet.consume(conn, tenant, enrollment["reservation_id"])
    return finish_seat(conn, tenant, enrollment["id"], "consume", "first course start")


def release_authorization(conn, tenant, enrollment, reason):
    if enrollment["reservation_id"]:
        return wallet.release(conn, tenant, enrollment["reservation_id"], reason)
    return finish_seat(conn, tenant, enrollment["id"], "release", reason)


def authorization_view(conn, tenant, enrollment):
    held = one(conn, ledger, tenant, ledger.c.enrollment_id == enrollment["id"], ledger.c.kind == "reserve")
    reservation = one(conn, m.reservations, tenant, m.reservations.c.id == enrollment["reservation_id"]) if enrollment["reservation_id"] else None
    return {"source": enrollment["source"], "entitlement_id": held["entitlement_id"] if held else None,
            "unit": "enrollment_seat" if held else "point", "quantity": 1 if held else (reservation["quantity"] if reservation else None),
            "expires_at": enrollment["expires_at"]}


def learner_is_active(conn, tenant, learner_id):
    member = one(conn, m.memberships, None, m.memberships.c.tenant_id == tenant,
                 m.memberships.c.user_id == learner_id, m.memberships.c.role == "learner", m.memberships.c.active.is_(True))
    return bool(member and one(conn, m.users, None, m.users.c.id == learner_id, m.users.c.active.is_(True)))


def release_unstarted_for_learner(conn, tenant_id, learner_id, reason):
    released = []
    for row in all_rows(conn, m.enrollments, tenant_id, m.enrollments.c.learner_id == learner_id,
                        m.enrollments.c.status == "assigned"):
        release_authorization(conn, tenant_id, row, reason)
        change(conn, m.enrollments, tenant_id, row["id"], status="cancelled")
        released.append(row["id"])
    return released


def expire_authorizations(conn, tenant):
    for row in all_rows(conn, m.enrollments, tenant, m.enrollments.c.status == "assigned"):
        inactive = not learner_is_active(conn, tenant, row["learner_id"])
        expired = aware(row["expires_at"]) <= m.now()
        if inactive or expired:
            reason = "learner membership inactive" if inactive else "unstarted course authorization expired"
            release_authorization(conn, tenant, row, reason)
            change(conn, m.enrollments, tenant, row["id"], status="cancelled" if inactive else "expired")
