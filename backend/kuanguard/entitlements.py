"""Finite service units, separate from the self-service points wallet."""
from . import models as m
from .db import add, all_rows, one
from .security import fail


def balance(conn, tenant, entitlement):
    rows = all_rows(conn, m.entitlement_ledger, tenant, m.entitlement_ledger.c.entitlement_id == entitlement["id"])
    totals = {kind: sum(row["quantity"] for row in rows if row["kind"] == kind) for kind in ("grant", "reserve", "release", "consume")}
    reserved = totals["reserve"]-totals["release"]-totals["consume"]
    return {**entitlement, "available": totals["grant"]-reserved-totals["consume"], "reserved": reserved, "consumed": totals["consume"]}


def reserve(conn, tenant, batch):
    existing = one(conn, m.entitlement_ledger, tenant, m.entitlement_ledger.c.batch_id == batch["id"], m.entitlement_ledger.c.kind == "reserve")
    if existing:
        return existing
    options = all_rows(conn, m.entitlements, tenant, m.entitlements.c.project_id == batch["project_id"],
                       m.entitlements.c.service_code == batch["service_code"], m.entitlements.c.unit == "batch")
    eligible = next((row for row in options if balance(conn, tenant, row)["available"] >= 1), None)
    if not eligible:
        fail(409, "SERVICE_ENTITLEMENT_REQUIRED", "此服務可用批次額度不足，需先核定有限額度或追加委託。")
    return add(conn, m.entitlement_ledger, tenant, entitlement_id=eligible["id"], batch_id=batch["id"], kind="reserve", quantity=1,
               business_key=f"batch:{batch['id']}:reserve", reason="服務批次建立，預留一批次額度")


def finish(conn, tenant, batch, kind, reason):
    hold = one(conn, m.entitlement_ledger, tenant, m.entitlement_ledger.c.batch_id == batch["id"], m.entitlement_ledger.c.kind == "reserve")
    if not hold:
        if kind == "release":
            return None  # Legacy unscheduled batches have no reservation to release.
        hold = reserve(conn, tenant, batch)
    terminal = one(conn, m.entitlement_ledger, tenant, m.entitlement_ledger.c.batch_id == batch["id"], m.entitlement_ledger.c.kind.in_(["consume", "release"]))
    if terminal:
        if terminal["kind"] != kind:
            fail(409, "SERVICE_ENTITLEMENT_STATE", "此批次額度已結算，不能重複轉移。")
        return terminal
    return add(conn, m.entitlement_ledger, tenant, entitlement_id=hold["entitlement_id"], batch_id=batch["id"], kind=kind,
               quantity=hold["quantity"], business_key=f"batch:{batch['id']}:{kind}", reason=reason)
