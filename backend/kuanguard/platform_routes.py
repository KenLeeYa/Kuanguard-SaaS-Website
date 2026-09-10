"""Explicit platform administration; also protected by the internal deployment boundary."""
from typing import Literal

from fastapi import APIRouter, Depends, Request, Query
from pydantic import Field

from . import models as m, partner_models as p, adapters
from .db import add, all_rows, change, one, set_tenant
from .partner import PARTNER_ROLES, feature_values, require_platform
from .project_routes import Input
from .security import Context, context, fail, idempotent, paged

router = APIRouter()


def organization(ctx, tenant_id):
    require_platform(ctx)
    row = one(ctx.conn, p.organization_profiles, None, p.organization_profiles.c.tenant_id == tenant_id)
    if not row:
        fail(404, "ORGANIZATION_NOT_FOUND", "找不到組織。")
    return row


@router.get("/platform/overview")
def overview(ctx: Context = Depends(context)):
    require_platform(ctx)
    return {"organizations": len(all_rows(ctx.conn, p.organization_profiles)),
            "leads": len(all_rows(ctx.conn, p.platform_leads)), "integrations": adapters.health(),
            "products": all_rows(ctx.conn, p.product_registry), "events": all_rows(ctx.conn, p.analytics_daily),
            "features": all_rows(ctx.conn, p.feature_definitions), "production_ready": False}


@router.get("/platform/organizations")
def organizations(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    require_platform(ctx)
    rows = []
    for row in all_rows(ctx.conn, p.organization_profiles):
        tenant = one(ctx.conn, m.tenants, None, m.tenants.c.id == row["tenant_id"])
        rows.append({**row, "name": tenant["name"], "status": tenant["status"], "features": feature_values(ctx.conn, tenant["id"])})
    set_tenant(ctx.conn, ctx.tenant_id)
    return paged(rows, page, page_size)


class OrganizationInput(Input):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{1,78}[a-z0-9])$")
    kind: Literal["partner", "merchant"]
    partner_type: Literal["SI", "MSP", "MSSP", "RESELLER", "REFERRAL"] | None = None


@router.post("/platform/organizations", status_code=201)
def create_organization(payload: OrganizationInput, request: Request, ctx: Context = Depends(context)):
    require_platform(ctx)
    def run():
        tenant = add(ctx.conn, m.tenants, name=payload.name, verified=False)
        profile = add(ctx.conn, p.organization_profiles, tenant_id=tenant["id"], **payload.model_dump(exclude={"name"}))
        if payload.kind == "partner":
            set_tenant(ctx.conn, tenant["id"])
            add(ctx.conn, p.tenant_branding, tenant["id"], company_name=payload.name, footer="Powered by KUANGUARD", primary_color="#0F766E")
            add(ctx.conn, p.tenant_features, tenant["id"], code="partner_portal", enabled=True, reason="Explicit platform onboarding")
        set_tenant(ctx.conn, ctx.tenant_id)
        ctx.audit("platform.organization.create", tenant["id"], payload.kind)
        return profile
    return idempotent(ctx, request, "platform.organization.create", payload.model_dump(), run)


class OrganizationStatus(Input):
    expected_status: Literal["active", "suspended"]
    status: Literal["active", "suspended"]
    reason: str = Field(min_length=10, max_length=1000)


@router.post("/platform/organizations/{tenant_id}/status")
def set_status(tenant_id: str, payload: OrganizationStatus, ctx: Context = Depends(context)):
    organization(ctx, tenant_id)
    row = one(ctx.conn, m.tenants, None, m.tenants.c.id == tenant_id)
    if row["status"] != payload.expected_status:
        fail(409, "VERSION_CONFLICT", "企業狀態已變更。")
    change(ctx.conn, m.tenants, None, tenant_id, status=payload.status)
    ctx.audit("platform.organization.status", tenant_id, payload.reason,
              {"before": payload.expected_status, "after": payload.status})
    return {"status": payload.status}


class FeatureInput(Input):
    code: str = Field(max_length=80)
    enabled: bool
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=10, max_length=1000)


@router.post("/platform/organizations/{tenant_id}/features")
def set_feature(tenant_id: str, payload: FeatureInput, request: Request, ctx: Context = Depends(context)):
    organization(ctx, tenant_id)
    definition = one(ctx.conn, p.feature_definitions, None, p.feature_definitions.c.code == payload.code)
    if not definition or (payload.enabled and definition["status"] == "planned"):
        fail(409, "FEATURE_NOT_AVAILABLE", "尚在規劃的功能不能直接啟用。")
    def run():
        set_tenant(ctx.conn, tenant_id)
        row = one(ctx.conn, p.tenant_features, tenant_id, p.tenant_features.c.code == payload.code)
        if (row["version"] if row else 0) != payload.expected_version:
            fail(409, "VERSION_CONFLICT", "功能設定已變更。")
        values = {"enabled": payload.enabled, "version": payload.expected_version + 1, "reason": payload.reason}
        if row:
            change(ctx.conn, p.tenant_features, tenant_id, row["id"], **values)
            result = one(ctx.conn, p.tenant_features, tenant_id, p.tenant_features.c.id == row["id"])
        else:
            result = add(ctx.conn, p.tenant_features, tenant_id, code=payload.code, **values)
        set_tenant(ctx.conn, ctx.tenant_id)
        ctx.audit("platform.feature.change", tenant_id, payload.reason,
                  {"code": payload.code, "before": row["enabled"] if row else None, "after": payload.enabled})
        return result
    return idempotent(ctx, request, "platform.feature:" + tenant_id, payload.model_dump(), run)


@router.get("/platform/organizations/{tenant_id}/settings")
def organization_settings(tenant_id: str, ctx: Context = Depends(context)):
    row = organization(ctx, tenant_id)
    set_tenant(ctx.conn, tenant_id)
    result = {"organization": row, "features": all_rows(ctx.conn, p.tenant_features, tenant_id),
              "effective_features": feature_values(ctx.conn, tenant_id), "branding": one(ctx.conn, p.tenant_branding, tenant_id),
              "members": all_rows(ctx.conn, m.memberships, None, m.memberships.c.tenant_id == tenant_id)}
    set_tenant(ctx.conn, ctx.tenant_id)
    return result


class MemberInput(Input):
    user_id: str = Field(max_length=36)
    role: str = Field(max_length=80)
    active: bool
    reason: str = Field(min_length=10, max_length=1000)


@router.post("/platform/organizations/{tenant_id}/members")
def member(tenant_id: str, payload: MemberInput, request: Request, ctx: Context = Depends(context)):
    row = organization(ctx, tenant_id)
    allowed = PARTNER_ROLES if row["kind"] == "partner" else {"customer_contact", "customer_admin", "billing_manager", "training_manager", "campaign_manager", "learner"}
    if payload.role not in allowed or not one(ctx.conn, m.users, None, m.users.c.id == payload.user_id, m.users.c.active.is_(True)):
        fail(422, "INVALID_MEMBER", "請選擇已有明示身分綁定的使用者與有效角色。")
    def run():
        membership = one(ctx.conn, m.memberships, None, m.memberships.c.tenant_id == tenant_id,
                         m.memberships.c.user_id == payload.user_id, m.memberships.c.role == payload.role)
        if membership:
            change(ctx.conn, m.memberships, None, membership["id"], active=payload.active)
        else:
            membership = add(ctx.conn, m.memberships, tenant_id=tenant_id, user_id=payload.user_id, role=payload.role, active=payload.active)
        ctx.audit("platform.member.change", membership["id"], payload.reason,
                  {"tenant_id": tenant_id, "role": payload.role, "active": payload.active})
        return {"id": membership["id"], "active": payload.active}
    return idempotent(ctx, request, "platform.member:" + tenant_id, payload.model_dump(), run)


class PriceInput(Input):
    expected_version: int = Field(ge=1)
    unit_amount_minor: int = Field(ge=0, le=100000, strict=True)
    monthly_fee_minor: int = Field(ge=0, le=10000000, strict=True)
    buyout_fee_minor: int = Field(ge=0, le=10000000, strict=True)
    policy_reference: str = Field(min_length=8, max_length=160)
    note: str = Field(min_length=10, max_length=1000)


@router.post("/platform/commerce/pricing")
def pricing(payload: PriceInput, request: Request, ctx: Context = Depends(context)):
    require_platform(ctx)
    def run():
        row = one(ctx.conn, p.product_registry, None, p.product_registry.c.code == "merchant")
        if not row or row["version"] != payload.expected_version:
            fail(409, "VERSION_CONFLICT", "公開方案已變更。")
        new_price = row["pricing"] | payload.model_dump(exclude={"expected_version"}) | {"charge_enabled": False}
        change(ctx.conn, p.product_registry, None, row["id"], pricing=new_price, version=row["version"] + 1)
        ctx.audit("platform.commerce.pricing", row["id"], "Website projection only; source billing is authoritative",
                  {"before": row["pricing"], "after": new_price})
        return {"version": row["version"] + 1, "pricing": new_price, "source_billing_changed": False}
    return idempotent(ctx, request, "platform.commerce.pricing", payload.model_dump(), run)


@router.get("/platform/leads")
def leads(kind: Literal["merchant", "partner", "enterprise"] | None = None, ctx: Context = Depends(context),
          page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    require_platform(ctx)
    rows = all_rows(ctx.conn, p.platform_leads, None, *([p.platform_leads.c.kind == kind] if kind else []))
    return paged([{key: value for key, value in row.items() if key not in {"submission_hash", "payload_hash"}} for row in rows], page, page_size)


class LeadStatus(Input):
    status: Literal["new", "contacted", "qualified", "converted", "closed"]


@router.post("/platform/leads/{lead_id}/status")
def lead_status(lead_id: str, payload: LeadStatus, ctx: Context = Depends(context)):
    require_platform(ctx)
    row = one(ctx.conn, p.platform_leads, None, p.platform_leads.c.id == lead_id)
    if not row:
        fail(404, "LEAD_NOT_FOUND", "找不到需求。")
    change(ctx.conn, p.platform_leads, None, lead_id, status=payload.status, assignee=ctx.user_id)
    ctx.audit("platform.lead.status", lead_id, details={"before": row["status"], "after": payload.status})
    return {"status": payload.status}


@router.get("/platform/domains")
def domains(ctx: Context = Depends(context)):
    require_platform(ctx)
    return {"items": [{key: value for key, value in row.items() if key != "verification_hash"} for row in all_rows(ctx.conn, p.tenant_domains)]}


@router.get("/platform/users")
def users(ctx: Context = Depends(context)):
    require_platform(ctx)
    return {"items": [{"id": row["id"], "name": row["name"]} for row in all_rows(ctx.conn, m.users, None, m.users.c.active.is_(True))]}
