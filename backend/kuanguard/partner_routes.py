"""Partner management and public commerce catalogue; all business data remains in existing tenants."""
import base64
from datetime import datetime, timezone
from io import BytesIO
import json
import re
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from pydantic import Field, field_validator

from . import models as m, partner_models as p, wallet
from .config import settings
from .db import add, all_rows, aware, change, get_connection, one, set_tenant
from . import partner as scope
from .project_routes import Input
from .security import Context, context, create_session, digest, fail, idempotent, owned, paged

router = APIRouter()
EMAIL = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"


@router.get("/public/commerce")
def commerce(conn=Depends(get_connection)):
    product = one(conn, p.product_registry, None, p.product_registry.c.code == "merchant")
    if not product:
        fail(503, "CATALOGUE_PENDING", "商家方案尚未完成設定。")
    return product


@router.get("/public/portal")
def public_portal(request: Request, slug: str | None = Query(None, max_length=80), conn=Depends(get_connection)):
    partner = scope.resolve_partner(conn, request.headers.get("host", ""), slug)
    return {"partner": scope.public_branding(conn, partner), "central_auth": settings().central_auth_url}


class LeadInput(Input):
    kind: Literal["merchant", "partner", "enterprise"]
    name: str = Field(min_length=1, max_length=120)
    company: str = Field(min_length=1, max_length=160)
    email: str = Field(max_length=254, pattern=EMAIL)
    phone: str = Field(min_length=5, max_length=40, pattern=r"^[+0-9() #\-]+$")
    business_type: str = Field(min_length=1, max_length=80)
    store_count: int = Field(default=1, ge=1, le=100000, strict=True)
    message: str = Field(default="", max_length=3000)
    source: str = Field(default="website", max_length=160, pattern=r"^[a-zA-Z0-9/_\-]+$")
    utm: dict[str, str] = Field(default_factory=dict)
    website: str = Field(default="", max_length=200)  # Honeypot, not persisted.
    consent: Literal[True]

    @field_validator("utm")
    @classmethod
    def bounded_utm(cls, value):
        if not set(value).issubset({"utm_source", "utm_medium", "utm_campaign"}) or any(
            not re.fullmatch(r"[a-zA-Z0-9_\-]{1,80}", item) for item in value.values()
        ):
            raise ValueError("Only non-personal campaign tags are accepted")
        return value


@router.post("/public/leads", status_code=201)
def create_lead(payload: LeadInput, request: Request, conn=Depends(get_connection)):
    from .api import rate_limit
    rate_limit(request, "commerce-lead", 6)
    if not scope.valid_origin(conn, request.headers.get("origin", "")):
        fail(403, "ORIGIN_DENIED", "表單来源未獲允許。")
    if payload.website:
        fail(422, "FORM_REJECTED", "請重新填寫表單。")
    key = request.headers.get("idempotency-key", "")
    if not 16 <= len(key) <= 128:
        fail(400, "IDEMPOTENCY_REQUIRED", "表單需包含有效的提交識別碼。")
    values = payload.model_dump(exclude={"website", "consent"})
    hashed = digest(json.dumps(values, sort_keys=True, ensure_ascii=False))
    prior = one(conn, p.platform_leads, None, p.platform_leads.c.submission_hash == digest(key))
    if prior:
        if prior["payload_hash"] != hashed:
            fail(409, "IDEMPOTENCY_CONFLICT", "這個提交識別碼已用於不同內容。")
        return {"id": prior["id"], "status": "received", "email_sent": False}
    lead = add(conn, p.platform_leads, **values, submission_hash=digest(key), payload_hash=hashed)
    return {"id": lead["id"], "status": "received", "email_sent": False}


class AnalyticsInput(Input):
    event: Literal["merchant_apply", "partner_apply", "login_merchant", "login_partner", "contact_submit"]
    path: Literal["/", "/pricing", "/partners", "/login", "/merchant/apply", "/contact"]


@router.post("/public/events", status_code=202)
def analytics(payload: AnalyticsInput, request: Request, conn=Depends(get_connection)):
    from .api import rate_limit
    rate_limit(request, "aggregate-event", 30)
    if not scope.valid_origin(conn, request.headers.get("origin", "")):
        fail(403, "ORIGIN_DENIED", "事件來源未獲允許。")
    day = m.now().date().isoformat()
    table = p.analytics_daily
    row = one(conn, table, None, table.c.day == day, table.c.event == payload.event, table.c.path == payload.path)
    if row:
        conn.execute(table.update().where(table.c.id == row["id"]).values(count=table.c.count + 1))
    else:
        add(conn, table, day=day, **payload.model_dump())
    return {"recorded": True, "personal_identifiers_stored": False}


def customer_link(ctx, customer_id):
    row = scope.link_for(ctx.conn, ctx.tenant_id, customer_id)
    if not row:
        fail(404, "CUSTOMER_NOT_FOUND", "找不到屬於此夥伴的客戶。")
    return row


def customer_view(ctx, link):
    tenant = one(ctx.conn, m.tenants, None, m.tenants.c.id == link["customer_tenant_id"])
    set_tenant(ctx.conn, tenant["id"])
    projects = all_rows(ctx.conn, m.projects, tenant["id"])
    set_tenant(ctx.conn, ctx.tenant_id)
    grant = one(ctx.conn, p.partner_customer_access, ctx.tenant_id, p.partner_customer_access.c.customer_tenant_id == tenant["id"],
                p.partner_customer_access.c.user_id == ctx.user_id, p.partner_customer_access.c.active.is_(True),
                p.partner_customer_access.c.expires_at > m.now())
    return {**link, "name": tenant["name"], "status": tenant["status"], "project_count": len(projects),
            "can_enter": bool(grant), "owning_partner_id": ctx.tenant_id}


@router.get("/partner/dashboard")
def partner_dashboard(ctx: Context = Depends(context)):
    profile = scope.require_partner(ctx)
    customers = [customer_view(ctx, link) for link in all_rows(ctx.conn, p.partner_customers, ctx.tenant_id, p.partner_customers.c.active.is_(True))]
    finance = bool(ctx.roles.intersection({"partner_admin", "partner_finance"}))
    return {"partner": scope.public_branding(ctx.conn, profile), "customers": customers,
            "projects": sum(row["project_count"] for row in customers),
            "wallet": wallet.summary(ctx.conn, ctx.tenant_id) if finance else None,
            "features": scope.feature_values(ctx.conn, ctx.tenant_id), "commission_enabled": False}


@router.get("/partner/customers")
def customers(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    scope.require_partner(ctx)
    return paged([customer_view(ctx, row) for row in all_rows(ctx.conn, p.partner_customers, ctx.tenant_id,
                 p.partner_customers.c.active.is_(True))], page, page_size)


class CustomerInput(Input):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{1,78}[a-z0-9])$")
    customer_source: Literal["PARTNER", "REFERRAL", "PLATFORM"] = "PARTNER"
    contract_owner: str = Field(min_length=1, max_length=160)
    service_provider: str = Field(min_length=1, max_length=160)


@router.post("/partner/customers", status_code=201)
def create_customer(payload: CustomerInput, request: Request, ctx: Context = Depends(context)):
    scope.require_partner(ctx, "partner_admin", "partner_sales")
    def run():
        tenant = add(ctx.conn, m.tenants, name=payload.name, verified=False)
        add(ctx.conn, p.organization_profiles, tenant_id=tenant["id"], slug=payload.slug, kind="customer")
        row = add(ctx.conn, p.partner_customers, ctx.tenant_id, customer_tenant_id=tenant["id"],
                  customer_source=payload.customer_source, originating_partner_id=ctx.tenant_id,
                  account_manager_id=ctx.user_id, contract_owner=payload.contract_owner, service_provider=payload.service_provider)
        ctx.audit("partner.customer.create", row["id"], "New tenant; identity invitation requires explicit member binding")
        return row
    return idempotent(ctx, request, "partner.customer.create", payload.model_dump(), run)


@router.get("/partner/customers/{customer_id}/access")
def customer_access(customer_id: str, ctx: Context = Depends(context)):
    scope.require_partner(ctx, "partner_admin")
    customer_link(ctx, customer_id)
    grants = all_rows(ctx.conn, p.partner_customer_access, ctx.tenant_id, p.partner_customer_access.c.customer_tenant_id == customer_id)
    set_tenant(ctx.conn, customer_id)
    projects = [{"id": row["id"], "name": row["name"]} for row in all_rows(ctx.conn, m.projects, customer_id)]
    set_tenant(ctx.conn, ctx.tenant_id)
    members = all_rows(ctx.conn, m.memberships, None, m.memberships.c.tenant_id == ctx.tenant_id, m.memberships.c.active.is_(True))
    return {"items": grants, "projects": projects, "members": [{**row, "name": one(ctx.conn, m.users, None, m.users.c.id == row["user_id"])["name"]} for row in members]}


class AccessInput(Input):
    user_id: str = Field(max_length=36)
    roles: list[str] = Field(max_length=10)
    project_ids: list[str] = Field(max_length=500)
    active: bool
    expected_version: int = Field(ge=0)
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def expiry(cls, value):
        if not value.tzinfo or value <= m.now() or value > scope.default_expiry():
            raise ValueError("Access must expire within 90 days")
        return value.astimezone(timezone.utc)


@router.post("/partner/customers/{customer_id}/access")
def set_access(customer_id: str, payload: AccessInput, request: Request, ctx: Context = Depends(context)):
    scope.require_partner(ctx, "partner_admin")
    customer_link(ctx, customer_id)
    memberships = all_rows(ctx.conn, m.memberships, None, m.memberships.c.tenant_id == ctx.tenant_id,
                           m.memberships.c.user_id == payload.user_id, m.memberships.c.active.is_(True))
    ceiling = set().union(*(scope.DELEGATED_ROLES.get(row["role"], set()) for row in memberships))
    if not memberships or not set(payload.roles).issubset(ceiling) or (payload.active and not payload.roles):
        fail(403, "ROLE_CEILING", "客戶授權不能超過此人的夥伴職務權限。")
    set_tenant(ctx.conn, customer_id)
    projects = {row["id"] for row in all_rows(ctx.conn, m.projects, customer_id)}
    set_tenant(ctx.conn, ctx.tenant_id)
    if not set(payload.project_ids).issubset(projects):
        fail(404, "PROJECT_SCOPE_DENIED", "包含不屬於此客戶的專案。")
    def run():
        row = one(ctx.conn, p.partner_customer_access, ctx.tenant_id, p.partner_customer_access.c.customer_tenant_id == customer_id,
                  p.partner_customer_access.c.user_id == payload.user_id)
        if (row["version"] if row else 0) != payload.expected_version:
            fail(409, "VERSION_CONFLICT", "授權已變更，請重新載入。")
        values = payload.model_dump(exclude={"expected_version", "user_id"}) | {"version": payload.expected_version + 1}
        if row:
            change(ctx.conn, p.partner_customer_access, ctx.tenant_id, row["id"], **values)
            result = owned(ctx, p.partner_customer_access, row["id"])
        else:
            result = add(ctx.conn, p.partner_customer_access, ctx.tenant_id, customer_tenant_id=customer_id, user_id=payload.user_id, **values)
        ctx.audit("partner.access.change", result["id"], details={"before": jsonable_encoder(row), "after": jsonable_encoder(result)})
        return result
    return idempotent(ctx, request, "partner.access:" + customer_id, payload.model_dump(), run)


@router.post("/partner/customers/{customer_id}/enter")
def enter_customer(customer_id: str, request: Request, response: Response, ctx: Context = Depends(context)):
    scope.require_partner(ctx)
    grant = scope.effective_access(ctx.conn, ctx.tenant_id, customer_id, ctx.user_id)
    customer = one(ctx.conn, m.tenants, None, m.tenants.c.id == customer_id, m.tenants.c.status == "active")
    if not customer:
        fail(403, "CUSTOMER_INACTIVE", "客戶企業已停用。")
    old = one(ctx.conn, m.sessions, None, m.sessions.c.token_hash == digest(request.cookies.get("kg_session", "")))
    change(ctx.conn, m.sessions, None, old["id"], revoked=True)
    csrf = create_session(ctx.conn, ctx.user_id, customer_id, response, request.headers["host"], ctx.tenant_id, True)
    ctx.audit("partner.workspace.enter", customer_id)
    return {"csrf_token": csrf, "roles": grant["roles"], "redirect": "/partner/workspace/overview"}


@router.post("/partner/return")
def return_partner(request: Request, response: Response, ctx: Context = Depends(context)):
    if not ctx.partner_id or not ctx.partner_grant_id:
        fail(403, "DELEGATION_REQUIRED", "目前不是委派的客戶工作階段。")
    old = one(ctx.conn, m.sessions, None, m.sessions.c.token_hash == digest(request.cookies.get("kg_session", "")))
    change(ctx.conn, m.sessions, None, old["id"], revoked=True)
    csrf = create_session(ctx.conn, ctx.user_id, ctx.partner_id, response, request.headers["host"], ctx.partner_id)
    ctx.audit("partner.workspace.return", ctx.partner_id)
    return {"csrf_token": csrf, "redirect": "/partner"}


@router.get("/partner/credits")
def partner_credits(ctx: Context = Depends(context)):
    scope.require_partner(ctx, "partner_admin", "partner_finance")
    return {**wallet.summary(ctx.conn, ctx.tenant_id), "allocations": all_rows(ctx.conn, p.credit_allocations, ctx.tenant_id)}


class AllocationInput(Input):
    quantity: int = Field(ge=1, le=1000000, strict=True)
    reason: str = Field(min_length=10, max_length=1000)


@router.post("/partner/customers/{customer_id}/credits")
def allocate_credits(customer_id: str, payload: AllocationInput, request: Request, ctx: Context = Depends(context)):
    scope.require_partner(ctx, "partner_finance")
    customer_link(ctx, customer_id)
    if not one(ctx.conn, m.tenants, None, m.tenants.c.id == customer_id, m.tenants.c.status == "active"):
        fail(409, "CUSTOMER_INACTIVE", "客戶企業已停用。")
    def run():
        for tenant_id in sorted({ctx.tenant_id, customer_id}):
            set_tenant(ctx.conn, tenant_id, True)
            if wallet.get_wallet(ctx.conn, tenant_id)["frozen"]:
                fail(409, "WALLET_FROZEN", "來源或目的錢包已凍結。")
        set_tenant(ctx.conn, ctx.tenant_id)
        lots = sorted(all_rows(ctx.conn, m.point_lots, ctx.tenant_id, m.point_lots.c.expires_at > m.now()),
                      key=lambda row: (aware(row["expires_at"]), row["id"]))
        remaining, sources = payload.quantity, []
        for lot in lots:
            take = min(remaining, wallet.balances(ctx.conn, ctx.tenant_id, lot["id"])["available"])
            if take > 0:
                sources.append((lot, take))
                remaining -= take
        if remaining:
            fail(409, "INSUFFICIENT_POINTS", "來源可用點數不足。")
        allocation_id, destinations = m.uid(), []
        for lot, quantity in sources:
            wallet.entry(ctx.conn, ctx.tenant_id, lot["id"], "allocate-out", "allocation:" + allocation_id,
                         reason=payload.reason, available_delta=-quantity)
            set_tenant(ctx.conn, customer_id)
            destination = wallet.grant(ctx.conn, customer_id, quantity, "partner-allocation:" + allocation_id,
                                       purpose=lot["purpose"], expires_at=lot["expires_at"])
            destinations.append({"lot_id": destination["id"], "quantity": quantity})
            add(ctx.conn, m.audit_events, customer_id, actor_id=ctx.user_id, action="partner.credits.receive",
                resource_id=allocation_id, trace_id=ctx.trace_id, summary=payload.reason)
            set_tenant(ctx.conn, ctx.tenant_id)
        record = add(ctx.conn, p.credit_allocations, ctx.tenant_id, id=allocation_id, customer_tenant_id=customer_id,
                     quantity=payload.quantity, source_lots=[{"lot_id": lot["id"], "quantity": amount} for lot, amount in sources],
                     destination_lots=destinations, actor_id=ctx.user_id, reason=payload.reason)
        ctx.audit("partner.credits.allocate", allocation_id, payload.reason)
        return record
    return idempotent(ctx, request, "partner.credits:" + customer_id, payload.model_dump(), run)


@router.get("/partner/branding")
def branding(ctx: Context = Depends(context)):
    scope.require_partner(ctx, "partner_admin")
    return one(ctx.conn, p.tenant_branding, ctx.tenant_id)


class BrandingInput(Input):
    expected_version: int = Field(ge=1)
    company_name: str = Field(min_length=1, max_length=120)
    legal_name: str = Field(default="", max_length=160)
    support_email: str = Field(default="", max_length=254)
    support_phone: str = Field(default="", max_length=40)
    footer: str = Field(default="Powered by KUANGUARD", max_length=300)
    primary_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    logo_asset_id: str | None = Field(default=None, max_length=36)
    favicon_asset_id: str | None = Field(default=None, max_length=36)

    @field_validator("company_name", "legal_name", "support_email", "support_phone", "footer")
    @classmethod
    def plain_text(cls, value):
        if any(char in value for char in "<>\x00") or any(ord(char) < 32 for char in value):
            raise ValueError("Branding fields accept plain text only")
        return value

    @field_validator("support_email")
    @classmethod
    def support_address(cls, value):
        if value and not re.fullmatch(EMAIL, value):
            raise ValueError("Invalid support email")
        return value


@router.post("/partner/branding")
def save_branding(payload: BrandingInput, request: Request, ctx: Context = Depends(context)):
    scope.require_partner(ctx, "partner_admin")
    scope.require_feature(ctx.conn, ctx.tenant_id, "white_label")
    def run():
        row = one(ctx.conn, p.tenant_branding, ctx.tenant_id)
        if not row or row["version"] != payload.expected_version:
            fail(409, "VERSION_CONFLICT", "品牌設定已變更，請重新載入。")
        for asset_id in (payload.logo_asset_id, payload.favicon_asset_id):
            if asset_id:
                owned(ctx, p.branding_assets, asset_id)
        values = payload.model_dump(exclude={"expected_version"}) | {"version": row["version"] + 1}
        change(ctx.conn, p.tenant_branding, ctx.tenant_id, row["id"], **values)
        ctx.audit("partner.branding.change", row["id"], details={"before": row, "after": values})
        return owned(ctx, p.tenant_branding, row["id"])
    return idempotent(ctx, request, "partner.branding", payload.model_dump(), run)


class AssetInput(Input):
    content_base64: str = Field(min_length=1, max_length=700000)


@router.post("/partner/branding/assets", status_code=201)
def upload_brand_asset(payload: AssetInput, request: Request, ctx: Context = Depends(context)):
    from PIL import Image, UnidentifiedImageError
    scope.require_partner(ctx, "partner_admin")
    scope.require_feature(ctx.conn, ctx.tenant_id, "white_label")
    if settings().storage_provider != "local":
        fail(503, "BRANDING_STORAGE_PENDING", "品牌圖檔儲存供應商尚未啟用。")
    try:
        raw = base64.b64decode(payload.content_base64, validate=True)
        with Image.open(BytesIO(raw)) as source:
            if source.format not in {"PNG", "JPEG", "WEBP"} or source.width * source.height > 4_000_000 or len(raw) > 500000:
                raise ValueError()
            source.load()
            image = source.convert("RGBA")
            image.thumbnail((1024, 1024))
            output = BytesIO()
            image.save(output, "PNG")
            sanitized = output.getvalue()
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        fail(422, "INVALID_BRAND_IMAGE", "請上傳 500 KB 以內的 PNG、JPEG 或 WebP，最多 400 萬像素。")
    sha = digest(sanitized)
    existing = one(ctx.conn, p.branding_assets, ctx.tenant_id, p.branding_assets.c.sha256 == sha)
    if existing:
        return {"id": existing["id"], "sha256": sha}
    key = f"{ctx.tenant_id}/branding/{sha}.png"
    target = settings().local_data_dir / key
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(sanitized)
    row = add(ctx.conn, p.branding_assets, ctx.tenant_id, object_key=key, sha256=sha, media_type="image/png", size=len(sanitized))
    ctx.audit("partner.branding.upload", row["id"])
    return {"id": row["id"], "sha256": sha}


@router.get("/public/branding/{tenant_id}/{asset_id}")
def brand_image(tenant_id: str, asset_id: str, request: Request, conn=Depends(get_connection)):
    scope.active_partner(conn, tenant_id)
    host_partner = scope.resolve_partner(conn, request.headers.get("host", ""))
    if host_partner and host_partner["tenant_id"] != tenant_id:
        fail(404, "NOT_FOUND", "找不到品牌圖檔。")
    set_tenant(conn, tenant_id)
    branding = one(conn, p.tenant_branding, tenant_id)
    if not branding or asset_id not in {branding["logo_asset_id"], branding["favicon_asset_id"]}:
        fail(404, "NOT_FOUND", "找不到已發布的品牌圖檔。")
    asset = one(conn, p.branding_assets, tenant_id, p.branding_assets.c.id == asset_id)
    if not asset:
        fail(404, "NOT_FOUND", "找不到品牌圖檔。")
    data = (settings().local_data_dir / asset["object_key"]).read_bytes()
    if digest(data) != asset["sha256"]:
        fail(409, "ASSET_INTEGRITY", "品牌圖檔驗證失敗。")
    return Response(data, media_type="image/png", headers={"Content-Security-Policy": "default-src 'none'"})


@router.get("/partner/domains")
def domains(ctx: Context = Depends(context)):
    scope.require_partner(ctx, "partner_admin")
    return {"items": [{key: value for key, value in row.items() if key != "verification_hash"} for row in
            all_rows(ctx.conn, p.tenant_domains, None, p.tenant_domains.c.tenant_id == ctx.tenant_id)]}


class DomainInput(Input):
    domain: str = Field(min_length=4, max_length=253)


@router.post("/partner/domains", status_code=201)
def register_domain(payload: DomainInput, request: Request, ctx: Context = Depends(context)):
    scope.require_partner(ctx, "partner_admin")
    scope.require_feature(ctx.conn, ctx.tenant_id, "custom_domain")
    # Verification token is returned exactly once; retry cannot retrieve a secret from idempotency storage.
    row, token = scope.new_domain(ctx.conn, ctx.tenant_id, payload.domain)
    ctx.audit("partner.domain.register", row["id"], payload.domain)
    return {"id": row["id"], "status": row["status"], "txt_name": "_kuanguard-verification." + row["domain"],
            "txt_value": token, "cname": row["expected_cname"], "token_shown_once": True}


class VersionInput(Input):
    expected_version: int = Field(ge=1)


@router.post("/partner/domains/{domain_id}/challenge")
def rotate_domain_challenge(domain_id: str, payload: VersionInput, ctx: Context = Depends(context)):
    import secrets
    scope.require_partner(ctx, "partner_admin")
    scope.require_feature(ctx.conn, ctx.tenant_id, "custom_domain")
    row = one(ctx.conn, p.tenant_domains, None, p.tenant_domains.c.id == domain_id, p.tenant_domains.c.tenant_id == ctx.tenant_id)
    if not row:
        fail(404, "DOMAIN_NOT_FOUND", "找不到網域。")
    if row["version"] != payload.expected_version or row["status"] not in {"PENDING", "VERIFYING", "FAILED", "DISABLED"}:
        fail(409, "VERSION_CONFLICT", "先停用使用中的網域，才能重新產生驗證。")
    token = secrets.token_urlsafe(32)
    change(ctx.conn, p.tenant_domains, None, domain_id, verification_hash=digest(token), status="PENDING",
           verified_at=None, tls_status="pending", version=row["version"] + 1, updated_at=m.now(), expected_cname=settings().custom_domain_target or None)
    ctx.audit("partner.domain.challenge", domain_id)
    return {"id": domain_id, "txt_name": "_kuanguard-verification." + row["domain"], "txt_value": token,
            "cname": settings().custom_domain_target or None, "version": row["version"] + 1}


@router.post("/partner/domains/{domain_id}/verify")
def verify_domain(domain_id: str, payload: VersionInput, request: Request, ctx: Context = Depends(context)):
    from .api import rate_limit
    scope.require_partner(ctx, "partner_admin")
    scope.require_feature(ctx.conn, ctx.tenant_id, "custom_domain")
    rate_limit(request, "domain-verification", 5)
    row = one(ctx.conn, p.tenant_domains, None, p.tenant_domains.c.id == domain_id, p.tenant_domains.c.tenant_id == ctx.tenant_id)
    if not row:
        fail(404, "DOMAIN_NOT_FOUND", "找不到網域。")
    if row["version"] != payload.expected_version or row["status"] == "DISABLED":
        fail(409, "VERSION_CONFLICT", "網域狀態已變更。")
    target = row["expected_cname"] or settings().custom_domain_target
    evidence = scope.verify_domain_transport(row["domain"], row["verification_hash"], target)
    active = all(evidence.values())
    change(ctx.conn, p.tenant_domains, None, row["id"], status="ACTIVE" if active else "VERIFYING",
           verified_at=m.now() if evidence["ownership"] else None, tls_status="active" if evidence["tls"] else "pending",
           expected_cname=target, updated_at=m.now(), version=row["version"] + 1)
    ctx.audit("partner.domain.verify", row["id"], details=evidence)
    return {"status": "ACTIVE" if active else "VERIFYING", "version": row["version"] + 1, "evidence": evidence}


@router.post("/partner/domains/{domain_id}/disable")
def disable_domain(domain_id: str, payload: VersionInput, ctx: Context = Depends(context)):
    scope.require_partner(ctx, "partner_admin")
    row = one(ctx.conn, p.tenant_domains, None, p.tenant_domains.c.id == domain_id, p.tenant_domains.c.tenant_id == ctx.tenant_id)
    if not row:
        fail(404, "DOMAIN_NOT_FOUND", "找不到網域。")
    if row["version"] != payload.expected_version:
        fail(409, "VERSION_CONFLICT", "網域狀態已變更。")
    change(ctx.conn, p.tenant_domains, None, domain_id, status="DISABLED", version=row["version"] + 1, updated_at=m.now())
    ctx.audit("partner.domain.disable", domain_id)
    return {"status": "DISABLED", "version": row["version"] + 1}


@router.get("/partner/audit")
def partner_audit(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    scope.require_partner(ctx, "partner_admin")
    return paged(sorted(all_rows(ctx.conn, m.audit_events, ctx.tenant_id), key=lambda row: row["created_at"], reverse=True), page, page_size)


@router.get("/partner/commissions")
def commissions(ctx: Context = Depends(context)):
    scope.require_partner(ctx, "partner_admin", "partner_finance")
    return {"enabled": False, "rules": all_rows(ctx.conn, p.partner_commission_rules, ctx.tenant_id),
            "records": all_rows(ctx.conn, p.partner_commission_records, ctx.tenant_id),
            "settlements": all_rows(ctx.conn, p.partner_settlements, ctx.tenant_id)}
