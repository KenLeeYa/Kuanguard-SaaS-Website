"""Customer requests and explicit operator review; destructive erasure remains offline."""
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field, field_validator
from sqlalchemy import select

from . import models as m
from .db import add, all_rows, change
from .lifecycle import canonical, offboard, offboard_manifest
from .project_routes import Input, project_rows, publication_rows, published_findings
from .security import Context, context, digest, fail, idempotent, owned

router = APIRouter(tags=["data lifecycle"])


class LifecycleRequest(Input):
    kind: Literal["data_export", "tenant_offboard"]
    reason: str = Field(min_length=5, max_length=1000)


class PlanInput(Input):
    request_id: str


class ExecuteInput(Input):
    plan_id: str
    expected_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmation: Literal["REVOKE_CUSTOMER_ACCESS_KEEP_DATA"]


class RetentionInput(Input):
    request_id: str
    days: int = Field(ge=0, le=36500, strict=True)
    backup_expiry: datetime
    reference: str = Field(min_length=8, max_length=500)
    legal_hold_cleared: Literal[True]
    financial_settlement_confirmed: Literal[True]

    @field_validator("backup_expiry")
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None:
            raise ValueError("Explicit timezone required")
        return value


def manager(ctx):
    ctx.require("pm")
    ctx.require("finance")


@router.get("/customer/lifecycle/requests")
def customer_requests(ctx: Context = Depends(context)):
    ctx.require("customer_admin")
    return {"items": all_rows(ctx.conn, m.deletion_requests, ctx.tenant_id,
            m.deletion_requests.c.requested_by == ctx.user_id)}


@router.post("/customer/lifecycle/requests")
def create_request(payload: LifecycleRequest, request: Request, ctx: Context = Depends(context)):
    ctx.require("customer_admin")

    def create():
        row = add(ctx.conn, m.deletion_requests, ctx.tenant_id, data_class=payload.kind,
                  reason=payload.reason, requested_by=ctx.user_id)
        ctx.audit("lifecycle.request", row["id"], f"kind={payload.kind}; requested by authenticated customer admin")
        return row

    return idempotent(ctx, request, "lifecycle.request", payload.model_dump(), create)


@router.get("/internal/lifecycle")
def lifecycle_overview(ctx: Context = Depends(context)):
    manager(ctx)
    return {"tenant_status": ctx.tenant["status"], "requests": all_rows(ctx.conn, m.deletion_requests, ctx.tenant_id),
            "notice": "退場保留帳本與報告；刪除另須核定保存、財務結清、備份淘汰和精確清冊。"}


@router.post("/internal/lifecycle/plan")
def create_plan(payload: PlanInput, request: Request, ctx: Context = Depends(context)):
    manager(ctx)
    row = owned(ctx, m.deletion_requests, payload.request_id)
    if row["data_class"] != "tenant_offboard" or row["status"] != "requested":
        fail(409, "LIFECYCLE_REQUEST_STATE", "此申請不在待處理的企業退場狀態。")

    def create():
        manifest = offboard_manifest(ctx.conn, ctx.tenant_id)
        plan = add(ctx.conn, m.lifecycle_plans, ctx.tenant_id, request_id=row["id"], kind="offboard",
                   manifest=manifest, digest=digest(canonical(manifest)), actor_id=ctx.user_id,
                   expires_at=m.now()+timedelta(minutes=10))
        ctx.audit("lifecycle.plan", plan["id"], f"manifest={plan['digest']}")
        return plan

    return idempotent(ctx, request, "lifecycle.plan", payload.model_dump(), create)


@router.post("/internal/lifecycle/offboard")
def execute_offboard(payload: ExecuteInput, request: Request, ctx: Context = Depends(context)):
    manager(ctx)
    plan = owned(ctx, m.lifecycle_plans, payload.plan_id)
    if plan["digest"] != payload.expected_digest or plan["kind"] != "offboard":
        fail(409, "LIFECYCLE_PLAN_MISMATCH", "請核對本次實際退場差異。")
    return idempotent(ctx, request, f"lifecycle.offboard:{plan['id']}", payload.model_dump(), lambda: offboard(ctx, plan))


@router.post("/internal/lifecycle/retention")
def approve_retention(payload: RetentionInput, request: Request, ctx: Context = Depends(context)):
    manager(ctx)
    row = owned(ctx, m.deletion_requests, payload.request_id)

    def approve():
        if ctx.tenant["status"] != "offboarding" or row["status"] != "offboarded":
            fail(409, "OFFBOARD_FIRST", "先完成退場及結清，再核定這份刪除申請。")
        policies = all_rows(ctx.conn, m.retention_policies, ctx.tenant_id, m.retention_policies.c.data_class == "tenant_all")
        if policies:
            fail(409, "RETENTION_ALREADY_APPROVED", "此企業已有保存核定，請依原核定清冊處理。")
        policy = add(ctx.conn, m.retention_policies, ctx.tenant_id, data_class="tenant_all", days=payload.days, version=1, approved=True)
        change(ctx.conn, m.deletion_requests, ctx.tenant_id, row["id"], status="erasure_approved", backup_expiry=payload.backup_expiry)
        ctx.audit("lifecycle.retention_approved", row["id"], f"policy={policy['id']}; reference={payload.reference}; legal_hold_cleared=true; financial_settlement_confirmed=true")
        return {"request_id": row["id"], "status": "erasure_approved", "data_erased": False, "executor": "offline exact manifest"}

    return idempotent(ctx, request, "lifecycle.retention", payload.model_dump(), approve)


@router.get("/customer/data-export")
def customer_export(request: Request,
                    section: Literal["projects", "reports", "findings", "orders", "training", "campaigns", "tickets"],
                    cursor: int = Query(0, ge=0), ctx: Context = Depends(context)):
    if set(request.query_params) - {"section", "cursor"}:
        fail(422, "EXPORT_SCOPE_FORBIDDEN", "匯出範圍由目前角色授權決定。")
    table = None
    conditions = []
    if section in {"projects", "reports", "findings"}:
        ctx.require("customer_contact")
        items = {"projects": project_rows, "reports": publication_rows, "findings": published_findings}[section](ctx)
        # Use the same published projections and project grants as the customer result routes.
    elif section == "orders":
        ctx.require("billing_manager")
        table = m.orders
    elif section == "training":
        ctx.require("training_manager")
        table = m.enrollments
    elif section == "campaigns":
        ctx.require("campaign_manager")
        table, conditions = m.campaigns, [m.campaigns.c.owner_id == ctx.user_id]
    else:
        ctx.require("customer_admin", "customer_contact", "training_manager", "campaign_manager", "billing_manager", "learner")
        table, conditions = m.tickets, [m.tickets.c.actor_id == ctx.user_id]
    if table is not None:
        items = [dict(row) for row in ctx.conn.execute(select(table).where(table.c.tenant_id == ctx.tenant_id, *conditions)
            .order_by(table.c.id).offset(cursor).limit(201)).mappings()]
        more = len(items) > 200
        items = items[:200]
    else:
        items = sorted(items, key=lambda item: item["id"])
        more = len(items) > cursor+200
        items = items[cursor:cursor+200]
    return {"format": "kuanguard-authorized-export-v1", "section": section, "tenant_id": ctx.tenant_id,
            "items": items, "next_cursor": cursor+200 if more else None, "generated_at": m.now(),
            "scope": "current actor grants; published customer projections only"}
