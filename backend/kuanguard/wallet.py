"""Integer append-only point accounting. Call within a serialized tenant DB transaction."""
from datetime import timedelta

from sqlalchemy import func, select

from . import models as m
from .db import add, all_rows, aware, change, one
from .security import fail

POLICY = "sandbox-2026-09-v1"
DELTAS = ("available_delta", "reserved_delta", "consumed_delta", "expired_delta", "refunded_delta")


def get_wallet(conn, tenant):
    wallet = one(conn, m.wallets, tenant)
    if not wallet:
        wallet = add(conn, m.wallets, tenant)
    conn.execute(select(m.wallets.c.id).where(m.wallets.c.id == wallet["id"]).with_for_update())
    return wallet


def balances(conn, tenant, lot_id):
    query = select(*(func.coalesce(func.sum(m.wallet_transactions.c[key]), 0).label(key) for key in DELTAS))
    row = conn.execute(query.where(m.wallet_transactions.c.tenant_id == tenant,
                                   m.wallet_transactions.c.lot_id == lot_id)).mappings().one()
    return {key.removesuffix("_delta"): int(row[key]) for key in DELTAS}


def entry(conn, tenant, lot_id, kind, business_key, reservation_id=None, reason="", **deltas):
    existing = one(conn, m.wallet_transactions, tenant, m.wallet_transactions.c.lot_id == lot_id,
                   m.wallet_transactions.c.business_key == business_key)
    if existing:
        return existing
    return add(conn, m.wallet_transactions, tenant, lot_id=lot_id, reservation_id=reservation_id,
               kind=kind, business_key=business_key, reason=reason, **{key: deltas.get(key, 0) for key in DELTAS})


def allocated(conn, tenant, lot_id=None):
    conditions = [m.wallet_transactions.c.kind == "allocate-out"]
    if lot_id:
        conditions.append(m.wallet_transactions.c.lot_id == lot_id)
    return -sum(row["available_delta"] for row in all_rows(conn, m.wallet_transactions, tenant, *conditions))


def grant(conn, tenant, quantity, source, purpose="all", expires_at=None, order_id=None, amount_minor=0):
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        fail(422, "INVALID_POINTS", "點數必須是正整數。")
    get_wallet(conn, tenant)
    if order_id:
        existing = one(conn, m.point_lots, tenant, m.point_lots.c.order_id == order_id)
        if existing:
            return existing
    lot = add(conn, m.point_lots, tenant, quantity=quantity, source=source, purpose=purpose,
              expires_at=expires_at or m.now() + timedelta(days=365), order_id=order_id, paid_amount_minor=amount_minor)
    entry(conn, tenant, lot["id"], "grant", f"grant:{lot['id']}", available_delta=quantity)
    return lot


def expire_lots(conn, tenant):
    for lot in all_rows(conn, m.point_lots, tenant, m.point_lots.c.expires_at <= m.now()):
        available = balances(conn, tenant, lot["id"])["available"]
        if available > 0:
            entry(conn, tenant, lot["id"], "expire", f"expire:{lot['id']}",
                  available_delta=-available, expired_delta=available)


def reserve(conn, tenant, purpose, business_id, quantity, expires_at):
    wallet = get_wallet(conn, tenant)
    if wallet["frozen"]:
        fail(409, "WALLET_FROZEN", "錢包已凍結，請聯絡帳務人員。")
    if quantity <= 0 or aware(expires_at) <= m.now():
        fail(422, "INVALID_RESERVATION", "預留點數與截止時間無效。")
    existing = one(conn, m.reservations, tenant, m.reservations.c.purpose == purpose,
                   m.reservations.c.business_id == business_id)
    if existing:
        if existing["quantity"] != quantity:
            fail(409, "RESERVATION_CONFLICT", "既有預留與本次數量不同。")
        if existing["status"] == "released":
            fail(409, "RESERVATION_RELEASED", "預留已取消，請建立新的業務版本。")
        return existing
    expire_lots(conn, tenant)
    lots = sorted(all_rows(conn, m.point_lots, tenant, m.point_lots.c.expires_at >= expires_at,
                           m.point_lots.c.purpose.in_(["all", purpose])), key=lambda lot: aware(lot["expires_at"]))
    allocations, remaining = [], quantity
    for lot in lots:
        take = min(remaining, balances(conn, tenant, lot["id"])["available"])
        if take > 0:
            allocations.append((lot, take))
            remaining -= take
        if remaining == 0:
            break
    if remaining:
        fail(409, "INSUFFICIENT_POINTS", "適用且在使用期限內的點數不足。")
    reservation = add(conn, m.reservations, tenant, purpose=purpose, business_id=business_id,
                      quantity=quantity, expires_at=expires_at, policy_version=POLICY)
    for lot, take in allocations:
        add(conn, m.reservation_lots, tenant, reservation_id=reservation["id"], lot_id=lot["id"], quantity=take)
        entry(conn, tenant, lot["id"], "reserve", f"reserve:{reservation['id']}", reservation["id"],
              available_delta=-take, reserved_delta=take)
    return reservation


def consume(conn, tenant, reservation_id, occurred_at=None):
    get_wallet(conn, tenant)
    reservation = one(conn, m.reservations, tenant, m.reservations.c.id == reservation_id)
    if not reservation:
        fail(404, "RESERVATION_NOT_FOUND", "找不到預留紀錄。")
    if reservation["status"] == "consumed":
        return reservation
    if reservation["status"] != "reserved":
        fail(409, "RESERVATION_INACTIVE", "預留已釋放。")
    event_time = aware(occurred_at) if occurred_at else m.now()
    if event_time > aware(reservation["expires_at"]) or event_time > m.now() + timedelta(minutes=5):
        fail(409, "RESERVATION_EXPIRED", "點數預留已過期或供應商時間無效，需人工對帳。")
    for allocation in all_rows(conn, m.reservation_lots, tenant, m.reservation_lots.c.reservation_id == reservation_id):
        entry(conn, tenant, allocation["lot_id"], "consume", f"consume:{reservation_id}", reservation_id,
              reserved_delta=-allocation["quantity"], consumed_delta=allocation["quantity"])
    change(conn, m.reservations, tenant, reservation_id, status="consumed")
    return {**reservation, "status": "consumed"}


def release(conn, tenant, reservation_id, reason):
    get_wallet(conn, tenant)
    reservation = one(conn, m.reservations, tenant, m.reservations.c.id == reservation_id)
    if not reservation or reservation["status"] != "reserved":
        return reservation
    for allocation in all_rows(conn, m.reservation_lots, tenant, m.reservation_lots.c.reservation_id == reservation_id):
        lot = one(conn, m.point_lots, tenant, m.point_lots.c.id == allocation["lot_id"])
        expired = aware(lot["expires_at"]) <= m.now()
        quantity = allocation["quantity"]
        entry(conn, tenant, lot["id"], "release_expired" if expired else "release", f"release:{reservation_id}",
              reservation_id, reason, reserved_delta=-quantity,
              available_delta=0 if expired else quantity, expired_delta=quantity if expired else 0)
    change(conn, m.reservations, tenant, reservation_id, status="released")
    return {**reservation, "status": "released"}


def summary(conn, tenant):
    wallet = get_wallet(conn, tenant)
    lots = []
    for lot in all_rows(conn, m.point_lots, tenant):
        balance = balances(conn, tenant, lot["id"])
        if aware(lot["expires_at"]) <= m.now():
            balance["expired"] += balance["available"]
            balance["available"] = 0
        lots.append({**lot, **balance})
    transactions = sorted(all_rows(conn, m.wallet_transactions, tenant), key=lambda row: row["created_at"], reverse=True)
    return {"available": sum(lot["available"] for lot in lots), "reserved": sum(lot["reserved"] for lot in lots),
            "consumed": sum(lot["consumed"] for lot in lots), "allocated": allocated(conn, tenant),
            "expiring": sum(lot["available"] for lot in lots if aware(lot["expires_at"]) < m.now() + timedelta(days=30)),
            "lots": lots, "transactions": transactions[:100], "transaction_total": len(transactions),
            "policy_version": POLICY, "sandbox": True, "frozen": wallet["frozen"]}


def refund_order(conn, tenant, order_id, amount_minor, reason, actor_id, chargeback=False):
    get_wallet(conn, tenant)
    order = one(conn, m.orders, tenant, m.orders.c.id == order_id)
    if not order or order["status"] not in {"paid", "partially_refunded"}:
        fail(409, "ORDER_NOT_REFUNDABLE", "訂單目前不能退款。")
    if amount_minor <= 0 or amount_minor % 100:
        fail(422, "REFUND_UNIT", "Sandbox 退款須為每點 100 分的整數倍。")
    refunded = sum(row["amount_minor"] for row in all_rows(conn, m.refunds, tenant, m.refunds.c.order_id == order_id,
                                                         m.refunds.c.status == "completed_sandbox"))
    if refunded + amount_minor > order["amount_minor"]:
        fail(409, "REFUND_EXCEEDS_PAYMENT", "退款不能超過付款金額。")
    lot = one(conn, m.point_lots, tenant, m.point_lots.c.order_id == order_id)
    quantity = amount_minor // 100
    balance = balances(conn, tenant, lot["id"])
    manual = chargeback or balance["available"] < quantity
    refund = add(conn, m.refunds, tenant, order_id=order_id, amount_minor=amount_minor, points=quantity,
                 status="manual_review" if manual else "completed_sandbox", reason=reason, actor_id=actor_id)
    if manual:
        wallet = one(conn, m.wallets, tenant)
        change(conn, m.wallets, tenant, wallet["id"], frozen=True)
        return refund
    entry(conn, tenant, lot["id"], "refund", f"refund:{refund['id']}", reason=reason,
          available_delta=-quantity, refunded_delta=quantity)
    change(conn, m.orders, tenant, order_id, status="refunded" if refunded + amount_minor == order["amount_minor"] else "partially_refunded")
    return refund
