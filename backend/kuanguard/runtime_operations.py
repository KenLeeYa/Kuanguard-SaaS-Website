"""Read-only operational counts. No raw findings, recipients, tokens or provider writes."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import and_, case, func, or_, select

from . import models as m, rate_limits
from .db import aware
from .security import Context, context, fail

router = APIRouter()


def snapshot(conn, tenant_id):
    current = m.now()
    jobs = {}
    for kind in ("report", "sandbox_mail"):
        due = and_(m.jobs.c.status == "queued", m.jobs.c.available_at <= current)
        expired = and_(m.jobs.c.status == "running",
                       or_(m.jobs.c.lease_until.is_(None), m.jobs.c.lease_until <= current))
        fields = [func.count(case((m.jobs.c.status == status, 1))).label(status)
                  for status in ("queued", "running", "failed", "dead_letter", "needs_review")]
        row = conn.execute(select(*fields, func.count(case((due, 1))).label("due_queued"),
            func.count(case((expired, 1))).label("expired_leases"),
            func.min(case((due, m.jobs.c.available_at))).label("oldest_due_at"))
            .where(m.jobs.c.tenant_id == tenant_id, m.jobs.c.kind == kind)).mappings().one()
        values = dict(row)
        oldest = aware(values.pop("oldest_due_at"))
        values["oldest_due_seconds"] = max(0, int((current-oldest).total_seconds())) if oldest else None
        jobs[kind] = values
    unknown = conn.scalar(select(func.count()).select_from(m.message_plans).where(
        m.message_plans.c.tenant_id == tenant_id, m.message_plans.c.status == "unknown"))
    paid = select(m.payments.c.id).where(m.payments.c.tenant_id == tenant_id,
                                        m.payments.c.order_id == m.orders.c.id).exists()
    granted = select(m.point_lots.c.id).where(m.point_lots.c.tenant_id == tenant_id,
                                             m.point_lots.c.order_id == m.orders.c.id).exists()
    mismatch = conn.scalar(select(func.count()).select_from(m.orders).where(
        m.orders.c.tenant_id == tenant_id, paid != granted))
    limits = rate_limits.health()
    attention = unknown or mismatch or limits["status"] == "unavailable" or any(
        values[name] for values in jobs.values() for name in ("failed", "dead_letter", "needs_review", "expired_leases"))
    return {"scope": "current_tenant", "status": "attention" if attention else "no_detected_issue",
            "checked_at": current, "jobs": jobs, "mail": {"unknown_outcomes": unknown, "automatic_resend": False},
            "payments": {"grant_mismatches": mismatch}, "rate_limits": limits,
            "production_ready": False, "external_alert_delivery": "not_configured",
            "unmeasured": ["worker_liveness_when_idle", "queue_sla", "render_memory_and_duration",
                           "backup_rpo", "external_provider_health", "tls_dns_and_costs"],
            "notice": "目前企業的維運彙總；未偵測到異常不代表完整健康或正式驗收通過。"}


@router.get("/internal/operations/health")
def operations_health(request: Request, ctx: Context = Depends(context)):
    ctx.require("pm", "platform_admin")
    if ctx.partner_grant_id or ctx.delegated_projects is not None:
        fail(403, "OPERATIONS_SCOPE_DENIED", "客戶專案委派不包含企業維運監控。")
    if request.query_params:
        fail(422, "INVALID_SCOPE", "維運監控只接受登入企業範圍，不接受查詢範圍參數。")
    return snapshot(ctx.conn, ctx.tenant_id)
