import hmac
import time
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from . import models as m, wallet
from .config import settings
from .db import add, all_rows, change, get_connection, one, set_tenant
from .project_routes import Input
from .security import Context, context, digest, fail, idempotent, owned, paged

router = APIRouter()


class OrderInput(Input):
    points: Literal[100, 500, 1000]


class RefundInput(Input):
    order_id: str
    amount_minor: int = Field(gt=0, strict=True)
    reason: str = Field(min_length=1, max_length=1000)


class PaymentEvent(Input):
    product_id: Literal["kuanguard"] = "kuanguard"
    event_id: str = Field(min_length=1, max_length=120)
    order_id: str
    merchant: str
    amount_minor: int = Field(gt=0, strict=True)
    currency: Literal["TWD"]
    status: Literal["paid", "failed", "refunded", "chargeback"]
    provider_ref: str = Field(min_length=1, max_length=120)


def process_payment(conn, event, payload_hash):
    mapping = one(conn, m.payment_routes, None, m.payment_routes.c.order_id == event.order_id)
    if not mapping or mapping["merchant"] != event.merchant:
        fail(400, "MERCHANT_ORDER_MISMATCH", "商店或訂單資料不符。")
    tenant = mapping["tenant_id"]
    set_tenant(conn, tenant, mutation=True)
    previous = one(conn, m.inbox, None, m.inbox.c.provider == "sandbox", m.inbox.c.event_id == event.event_id)
    if previous:
        if previous["payload_hash"] != payload_hash:
            fail(409, "EVENT_ID_CONFLICT", "相同事件識別碼的內容不一致。")
        return {"status": previous["status"], "duplicate": True}
    order = one(conn, m.orders, tenant, m.orders.c.id == event.order_id)
    if not order or event.currency != order["currency"]:
        fail(400, "PAYMENT_MISMATCH", "訂單幣別不符。")
    if event.status in {"paid", "failed", "chargeback"} and event.amount_minor != order["amount_minor"]:
        fail(400, "PAYMENT_AMOUNT_MISMATCH", "付款金額不符。")
    if event.status == "paid":
        payment = one(conn, m.payments, tenant, m.payments.c.order_id == order["id"])
        if payment and payment["provider_ref"] != event.provider_ref:
            fail(409, "PAYMENT_REFERENCE_MISMATCH", "訂單已有不同付款參照，需人工對帳。")
        if not payment:
            add(conn, m.payments, tenant, order_id=order["id"], provider_ref=event.provider_ref,
                amount_minor=event.amount_minor, currency=event.currency, status="paid")
            wallet.grant(conn, tenant, order["points"], "paid_sandbox", order_id=order["id"], amount_minor=order["amount_minor"])
            change(conn, m.orders, tenant, order["id"], status="paid")
            add(conn, m.invoices, tenant, order_id=order["id"])
        result = "processed"
    elif event.status == "failed":
        if order["status"] == "pending":
            change(conn, m.orders, tenant, order["id"], status="payment_failed")
        result = "ignored_late_failure" if order["status"] != "pending" else "processed"
    elif event.status in {"refunded", "chargeback"}:
        if order["status"] not in {"paid", "partially_refunded"}:
            # Roll back without inbox acknowledgment, allowing provider retry after the payment event arrives.
            fail(409, "PAYMENT_NOT_RECONCILED", "尚未對到原付款，請重送或人工對帳。")
        result = wallet.refund_order(conn, tenant, order["id"], event.amount_minor, f"provider:{event.event_id}",
                                     "payment-service", chargeback=event.status == "chargeback")["status"]
    add(conn, m.inbox, provider="sandbox", event_id=event.event_id, payload_hash=payload_hash, status=result, order_id=order["id"])
    add(conn, m.audit_events, tenant, actor_id="payment-service", action="payment.webhook", resource_id=order["id"], summary=f"event={event.event_id}; status={event.status}")
    return {"status": result, "duplicate": False, "sandbox": True}


@router.get("/customer/wallet")
def get_wallet(ctx: Context = Depends(context)):
    ctx.require("billing_manager")
    return wallet.summary(ctx.conn, ctx.tenant_id)


@router.get("/customer/orders")
def get_orders(ctx: Context = Depends(context)):
    ctx.require("billing_manager")
    return paged(all_rows(ctx.conn, m.orders, ctx.tenant_id))


@router.post("/customer/wallet/orders")
def create_order(payload: OrderInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("billing_manager")
    if not ctx.tenant["verified"]:
        fail(403, "TENANT_VERIFICATION_REQUIRED", "企業管理權驗證完成後才可購點。")

    def run():
        row = add(ctx.conn, m.orders, ctx.tenant_id, points=payload.points, amount_minor=payload.points*100,
                  rate_version=wallet.POLICY, actor_id=ctx.user_id, terms="本機 sandbox：每點 TWD 1 元，365 日效期，未消耗且未預留點數可測試退款；不是真實價格或交易。")
        add(ctx.conn, m.payment_routes, tenant_id=ctx.tenant_id, order_id=row["id"])
        ctx.audit("order.create", row["id"], "sandbox; no real charge")
        return {**row, "sandbox": True}
    return idempotent(ctx, request, "order.create", payload.model_dump(), run)


@router.get("/customer/orders/{order_id}")
def get_order(order_id: str, ctx: Context = Depends(context)):
    ctx.require("billing_manager")
    row = owned(ctx, m.orders, order_id)
    if row["actor_id"] != ctx.user_id:
        fail(404, "ORDER_NOT_FOUND", "找不到此購點操作。")
    return row


@router.post("/development/payments/{order_id}/settle")
def settle(order_id: str, request: Request, ctx: Context = Depends(context)):
    if settings().app_env not in {"development", "test"}:
        fail(404, "NOT_FOUND", "找不到此操作。")
    ctx.require("billing_manager")
    order = owned(ctx, m.orders, order_id)

    def run():
        event = PaymentEvent(event_id=f"sandbox-paid:{order_id}", order_id=order_id, merchant="kuanguard-sandbox",
                             amount_minor=order["amount_minor"], currency="TWD", status="paid", provider_ref=f"sandbox:{order_id}")
        result = process_payment(ctx.conn, event, digest(event.model_dump_json()))
        return {**owned(ctx, m.orders, order_id), "payment_result": result, "sandbox": True}
    return idempotent(ctx, request, f"payment.settle:{order_id}", {}, run)


@router.post("/webhooks/payments/sandbox")
async def payment_webhook(request: Request, conn=Depends(get_connection)):
    if settings().app_env not in {"development", "test"} or settings().payment_provider != "sandbox":
        fail(404, "NOT_FOUND", "付款介面未啟用。")
    secret = settings().payment_webhook_secret
    if not secret:
        fail(503, "WEBHOOK_NOT_CONFIGURED", "尚未設定 sandbox webhook secret。")
    body = await request.body()
    if len(body) > 16384:
        fail(413, "PAYLOAD_TOO_LARGE", "回呼內容過大。")
    timestamp = request.headers.get("x-payment-timestamp", "")
    try:
        if abs(time.time()-int(timestamp)) > 300:
            raise ValueError()
    except ValueError:
        fail(401, "SIGNATURE_EXPIRED", "簽章時間無效。")
    signature = hmac.new(secret.encode(), timestamp.encode()+b"."+body, "sha256").hexdigest()
    if not hmac.compare_digest(signature, request.headers.get("x-payment-signature", "")):
        fail(401, "INVALID_SIGNATURE", "回呼簽章無效。")
    event = PaymentEvent.model_validate_json(body)
    return process_payment(conn, event, digest(body))


@router.get("/internal/billing")
def billing(ctx: Context = Depends(context)):
    ctx.require("finance")
    return {"wallet": wallet.summary(ctx.conn, ctx.tenant_id), "orders": all_rows(ctx.conn, m.orders, ctx.tenant_id),
            "payments": all_rows(ctx.conn, m.payments, ctx.tenant_id), "refunds": all_rows(ctx.conn, m.refunds, ctx.tenant_id),
            "invoices": all_rows(ctx.conn, m.invoices, ctx.tenant_id), "sandbox": True}


@router.post("/internal/billing/refunds")
def refund(payload: RefundInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("finance")
    owned(ctx, m.orders, payload.order_id)

    def run():
        row = wallet.refund_order(ctx.conn, ctx.tenant_id, payload.order_id, payload.amount_minor, payload.reason, ctx.user_id)
        ctx.audit("refund.request", row["id"], payload.reason)
        return row
    return idempotent(ctx, request, "refund.request", payload.model_dump(), run)


@router.get("/internal/billing/reconciliation")
def reconciliation(ctx: Context = Depends(context)):
    ctx.require("finance")
    problems = []
    for order in all_rows(ctx.conn, m.orders, ctx.tenant_id):
        payment = one(ctx.conn, m.payments, ctx.tenant_id, m.payments.c.order_id == order["id"])
        lot = one(ctx.conn, m.point_lots, ctx.tenant_id, m.point_lots.c.order_id == order["id"])
        if bool(payment) != bool(lot):
            problems.append({"order_id": order["id"], "code": "PAYMENT_GRANT_MISMATCH"})
    for lot in all_rows(ctx.conn, m.point_lots, ctx.tenant_id):
        values = wallet.balances(ctx.conn, ctx.tenant_id, lot["id"])
        if sum(values.values()) != lot["quantity"] or min(values.values()) < 0:
            problems.append({"lot_id": lot["id"], "code": "LEDGER_INVARIANT"})
    return {"status": "matched" if not problems else "needs_review", "problems": problems, "checked_at": m.now(), "sandbox": True}
