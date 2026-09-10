from collections import defaultdict, deque
from datetime import timedelta
import base64
import hashlib
import logging
import secrets
import time
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import Field, ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from . import adapters, models as m, wallet
from .access import protect_internal_boundary
from .billing_routes import router as billing_router
from .campaign_routes import router as campaign_router
from .catalog import SERVICE_CODES
from .config import settings
from .db import add, all_rows, change, get_connection, one, set_tenant
from .learning_routes import router as learning_router
from .project_routes import Input, batch_rows, customer_batch_view, internal, project_rows, publication_rows, published_findings, router as project_router
from .portfolio_routes import router as portfolio_router
from .operations_routes import router as operations_router
from .draft_routes import router as draft_router
from .lifecycle_routes import router as lifecycle_router
from .security import Context, context, create_session, digest, fail, idempotent, owned, paged
from .seed import PROFILES, fixed

app = FastAPI(title="KUANGUARD API", version="0.1.1", description="Private security service platform. Development providers explicitly labeled; production release gate closed.")
app.include_router(project_router)
app.include_router(billing_router)
app.include_router(learning_router)
app.include_router(campaign_router)
app.include_router(portfolio_router)
app.include_router(operations_router)
app.include_router(draft_router)
app.include_router(lifecycle_router)

_rates = defaultdict(deque)


def rate_limit(request, category, limit=20):
    key = (request.client.host if request.client else "unknown", category)
    queue = _rates[key]
    current = time.monotonic()
    while queue and queue[0] < current-60:
        queue.popleft()
    if len(queue) >= limit:
        fail(429, "RATE_LIMITED", "操作過於頻繁，請稍候再試。")
    queue.append(current)


def error_response(request, status, detail):
    if not isinstance(detail, dict):
        detail = {"code": "REQUEST_ERROR", "message": str(detail)}
    detail = {**detail, "trace_id": getattr(request.state, "trace_id", str(uuid4()))}
    return JSONResponse({"detail": detail}, status_code=status, headers={"Cache-Control": "no-store"})


@app.middleware("http")
async def boundary(request: Request, call_next):
    request.state.trace_id = str(uuid4())
    try:
        protect_internal_boundary(request.headers.get("host", ""), request.url.path, request.headers.get("cf-access-jwt-assertion", ""))
        declared = request.headers.get("content-length", "0")
        if not declared.isdigit() or int(declared) > 6_000_000:
            fail(413, "PAYLOAD_TOO_LARGE", "請求內容超過限制。")
        response = await call_next(request)
    except HTTPException as exc:
        response = error_response(request, exc.status_code, exc.detail)
    response.headers["X-Request-ID"] = request.state.trace_id
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Cookie, Origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return error_response(request, exc.status_code, exc.detail)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    fields = [".".join(str(part) for part in error["loc"]) for error in exc.errors()]
    return error_response(request, 422, {"code": "INVALID_INPUT", "message": "請檢查輸入欄位。", "fields": fields})


@app.exception_handler(ValidationError)
async def provider_validation_error(request, exc):
    return error_response(request, 422, {"code": "INVALID_PROVIDER_PAYLOAD", "message": "供應商資料格式不符。"})


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return error_response(request, 409, {"code": "DATA_CONFLICT", "message": "資料關聯或版本衝突，請重新整理。"})


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logging.getLogger("kuanguard").error("trace=%s error_type=%s", request.state.trace_id, type(exc).__name__)
    return error_response(request, 500, {"code": "INTERNAL_ERROR", "message": "處理未完成，請保留追查編號並稍後重試。"})


@app.get("/health")
def health(conn=Depends(get_connection)):
    conn.execute(text("SELECT 1"))
    return {"status": "ok", "product": "kuanguard", "environment": settings().app_env, "version": "0.1.1", "production_ready": False}


@app.get("/public/services")
def services(conn=Depends(get_connection)):
    return {"items": [{**service, "status": "inquiry"} for service in all_rows(conn, m.service_catalog)]}


class QuoteRequest(Input):
    company: str = Field(min_length=1, max_length=120)
    contact_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    services: list[str] = Field(min_length=1, max_length=7)
    scope: str = Field(min_length=1, max_length=10000)
    desired_date: str | None = Field(default=None, max_length=30)


@app.post("/public/quote-requests", status_code=201)
def quote_request(payload: QuoteRequest, request: Request, conn=Depends(get_connection)):
    rate_limit(request, "quote", 10)
    if not set(payload.services).issubset(SERVICE_CODES):
        fail(422, "INVALID_SERVICE", "請選擇有效服務。")
    row = add(conn, m.leads, **payload.model_dump())
    return {"id": row["id"], "status": row["status"], "message": "需求已收到，可於內部需求管理查看。", "email_sent": False}


def public_course(row):
    return {key: value for key, value in row.items() if key not in {"max_attempts", "pass_percent"}} | {"pricing_status": "inquiry", "synthetic": row["status"] == "development"}


@app.get("/public/courses")
@app.get("/public/course-previews")
def public_courses(conn=Depends(get_connection)):
    return paged([public_course(row) for row in all_rows(conn, m.courses, None, m.courses.c.status.in_(["published", "development"]))])


@app.get("/public/courses/{course_id}")
def course_preview(course_id: str, conn=Depends(get_connection)):
    from sqlalchemy import or_
    row = one(conn, m.courses, None, or_(m.courses.c.id == course_id, m.courses.c.slug == course_id))
    if not row:
        fail(404, "COURSE_NOT_FOUND", "找不到課程。")
    return public_course(row)


class LoginInput(Input):
    profile_key: str


@app.get("/auth/dev/profiles")
def profiles():
    if settings().app_env not in {"development", "test"} or settings().auth_provider != "development":
        fail(404, "NOT_FOUND", "開發登入未啟用。")
    return {"items": [{"key": key, "label": label, "roles": roles} for key, (_, label, roles) in PROFILES.items()], "development": True}


@app.post("/auth/dev/login")
def dev_login(payload: LoginInput, request: Request, response: Response, conn=Depends(get_connection)):
    if settings().app_env not in {"development", "test"} or settings().auth_provider != "development":
        fail(404, "NOT_FOUND", "開發登入未啟用。")
    rate_limit(request, "dev-login", 60)
    if request.headers.get("origin", "").rstrip("/") not in settings().origins:
        fail(403, "ORIGIN_DENIED", "登入來源未獲允許。")
    if payload.profile_key not in PROFILES:
        fail(400, "PROFILE_NOT_FOUND", "無效的開發角色。")
    suffix, label, roles = PROFILES[payload.profile_key]
    user = one(conn, m.users, None, m.users.c.id == fixed(payload.profile_key), m.users.c.active.is_(True))
    if not user:
        fail(503, "FIXTURE_MISSING", "請先完成 development seed。")
    csrf = create_session(conn, user["id"], fixed("tenant-"+suffix), response)
    return {"development": True, "csrf_token": csrf, "user": {"id": user["id"], "name": user["name"]},
            "roles": roles, "redirect": "/admin/portfolio" if "portfolio_owner" in roles else "/learn" if roles == ["learner"] else "/dashboard"}


@app.get("/auth/me")
def me(ctx: Context = Depends(context)):
    return {"user": {"id": ctx.user_id, "name": ctx.user["name"]}, "tenant": {"id": ctx.tenant_id, "name": ctx.tenant["name"]},
            "roles": sorted(ctx.roles), "csrf_token": ctx.csrf_token, "development": settings().app_env != "production", "product": "kuanguard"}


@app.post("/auth/logout")
def logout(request: Request, response: Response, ctx: Context = Depends(context)):
    token_hash = digest(request.cookies.get("kg_session", ""))
    row = one(ctx.conn, m.sessions, None, m.sessions.c.token_hash == token_hash)
    change(ctx.conn, m.sessions, ctx.tenant_id, row["id"], revoked=True)
    response.delete_cookie("kg_session", path="/")
    return {"status": "logged_out"}


@app.get("/auth/providers")
def providers():
    configured = settings().auth_provider == "oidc" and bool(settings().oidc_issuer and settings().oidc_client_id)
    return {"items": [{"id": "oidc", "label": "企業登入", "url": "/api/auth/oidc/start"}] if configured else []}


@app.get("/auth/oidc/start")
def oidc_start(conn=Depends(get_connection)):
    import httpx
    config = settings()
    if config.auth_provider != "oidc" or not config.oidc_issuer.startswith("https://"):
        fail(503, "OIDC_DISABLED", "企业登入尚未完成設定。")
    discovery = httpx.get(config.oidc_issuer.rstrip("/")+"/.well-known/openid-configuration", timeout=5).json()
    if discovery.get("issuer") != config.oidc_issuer or not discovery.get("authorization_endpoint", "").startswith("https://"):
        fail(503, "OIDC_METADATA_INVALID", "登入供應商設定不一致。")
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    add(conn, m.oidc_states, state_hash=digest(state), nonce=nonce, verifier=verifier, expires_at=m.now()+timedelta(minutes=5))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    url = discovery["authorization_endpoint"]+"?"+urlencode({"client_id": config.oidc_client_id,
        "redirect_uri": config.oidc_redirect_uri, "response_type": "code", "scope": "openid", "state": state, "nonce": nonce,
        "code_challenge": challenge, "code_challenge_method": "S256"})
    response = RedirectResponse(url, status_code=303)
    response.set_cookie("kg_oidc_state", state, httponly=True, secure=True, samesite="lax", max_age=300, path="/")
    return response


@app.get("/auth/oidc/callback")
def oidc_callback(code: str, state: str, request: Request, conn=Depends(get_connection)):
    import httpx
    import jwt
    import hmac
    from sqlalchemy import delete
    config = settings()
    if config.auth_provider != "oidc" or not hmac.compare_digest(state, request.cookies.get("kg_oidc_state", "")):
        fail(403, "OIDC_STATE_INVALID", "登入狀態驗證失敗。")
    pending = one(conn, m.oidc_states, None, m.oidc_states.c.state_hash == digest(state), m.oidc_states.c.expires_at > m.now())
    if not pending:
        fail(403, "OIDC_STATE_EXPIRED", "登入狀態已失效。")
    metadata = httpx.get(config.oidc_issuer.rstrip("/")+"/.well-known/openid-configuration", timeout=5).json()
    if metadata.get("issuer") != config.oidc_issuer or any(not metadata.get(key, "").startswith("https://") for key in ["token_endpoint", "jwks_uri"]):
        fail(503, "OIDC_METADATA_INVALID", "登入供應商設定不一致。")
    result = httpx.post(metadata["token_endpoint"], data={"grant_type": "authorization_code", "code": code, "client_id": config.oidc_client_id,
        "client_secret": config.oidc_client_secret, "redirect_uri": config.oidc_redirect_uri, "code_verifier": pending["verifier"]}, timeout=10)
    result.raise_for_status()
    token = result.json().get("id_token", "")
    try:
        key = jwt.PyJWKClient(metadata["jwks_uri"], timeout=5).get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256"], audience=config.oidc_client_id, issuer=config.oidc_issuer,
                            options={"require": ["iss", "sub", "aud", "exp", "iat", "nonce"]})
        if not hmac.compare_digest(claims["nonce"], pending["nonce"]):
            raise jwt.InvalidTokenError()
    except jwt.PyJWTError:
        fail(403, "OIDC_TOKEN_INVALID", "登入憑證驗證失敗。")
    user = one(conn, m.users, None, m.users.c.oidc_subject == f"{claims['iss']}|{claims['sub']}", m.users.c.active.is_(True))
    if not user:
        fail(403, "MEMBERSHIP_REQUIRED", "此身分尚未獲得企業邀請或角色授權。")
    memberships = all_rows(conn, m.memberships, None, m.memberships.c.user_id == user["id"], m.memberships.c.active.is_(True))
    if not memberships:
        fail(403, "MEMBERSHIP_REQUIRED", "此身分尚未獲授權。")
    conn.execute(delete(m.oidc_states).where(m.oidc_states.c.id == pending["id"]))
    tenant_id = memberships[0]["tenant_id"]
    roles = {membership["role"] for membership in memberships if membership["tenant_id"] == tenant_id}
    response = RedirectResponse(login_destination(roles, request.url.hostname), status_code=303)
    create_session(conn, user["id"], tenant_id, response)
    response.delete_cookie("kg_oidc_state")
    return response


def login_destination(roles, hostname):
    if roles.intersection({"portfolio_owner", "pm", "engineer", "reviewer", "finance"}):
        path = "/portfolio" if "portfolio_owner" in roles else "/overview"
        return path if hostname == "admin.kuanguard.com" else "/admin" + path
    if roles == {"learner"}:
        return "/learn/courses"
    return "/dashboard"


@app.get("/customer/dashboard")
def dashboard(ctx: Context = Depends(context)):
    ctx.require("customer_contact", "campaign_manager", "training_manager", "billing_manager", "customer_admin")
    projects = project_rows(ctx) if "customer_contact" in ctx.roles else []
    findings = published_findings(ctx) if "customer_contact" in ctx.roles else []
    approved_statistics = [row["statistics"] for row in publication_rows(ctx) if not row["superseded"]] if "customer_contact" in ctx.roles else []
    batches = batch_rows(ctx) if "customer_contact" in ctx.roles else []
    training = all_rows(ctx.conn, m.enrollments, ctx.tenant_id) if "training_manager" in ctx.roles else None
    campaigns = all_rows(ctx.conn, m.campaigns, ctx.tenant_id, m.campaigns.c.owner_id == ctx.user_id) if "campaign_manager" in ctx.roles else None
    risks = {level: sum(stats.get("severity_counts", {}).get(level, 0) for stats in approved_statistics) for level in ["Critical", "High", "Medium", "Low"]}
    risks.update(Informational=sum(stats.get("informational_count", 0) for stats in approved_statistics),
                 Unknown=sum(stats.get("unknown_count", 0) for stats in approved_statistics))
    return {"projects": projects, "upcoming": [customer_batch_view(row) for row in batches if row["start_at"]],
            "risks": risks,
            "published_findings": len(findings), "wallet": wallet.summary(ctx.conn, ctx.tenant_id) if "billing_manager" in ctx.roles else None,
            "training": {"assigned": len(training), "completed": sum(row["status"] == "completed" for row in training)} if training is not None else None,
            "campaigns": {"total": len(campaigns), "active": sum(row["status"] in {"scheduled", "observing"} for row in campaigns)} if campaigns is not None else None,
            "updated_at": m.now(), "notice": "合成示範資料；尚無已發布結果時不代表安全。", "services": all_rows(ctx.conn, m.service_catalog)}


@app.get("/internal/overview")
def overview(ctx: Context = Depends(context)):
    internal(ctx, "pm", "engineer", "reviewer", "finance", "portfolio_owner")
    batches = batch_rows(ctx) if ctx.roles.intersection({"pm", "engineer", "reviewer"}) else []
    return {"projects": project_rows(ctx) if batches else [], "batches": batches,
            "awaiting_review": sum(row["status"] == "awaiting_review" for row in batches),
            "delivered": sum(row["status"] == "delivered" for row in batches),
            "unassigned": sum(not row["engineer_id"] for row in batches),
            "today": [row for row in batches if row["start_at"] and row["start_at"].date() == m.now().date()],
            "integrations": adapters.health(), "updated_at": m.now(), "notice": "內部示範環境；七服務正式啟用尚待完整驗收。"}


@app.get("/internal/integrations")
def integrations(ctx: Context = Depends(context)):
    ctx.require("pm", "portfolio_owner", "platform_admin")
    return paged(adapters.health())


@app.get("/internal/jobs")
def jobs(ctx: Context = Depends(context)):
    internal(ctx, "pm", "engineer", "reviewer")
    return paged(all_rows(ctx.conn, m.jobs, None, m.jobs.c.tenant_id == ctx.tenant_id, m.jobs.c.kind.in_(["report", "sandbox_mail"])))


@app.post("/internal/jobs/{job_id}/retry")
def retry_job(job_id: str, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "reviewer")
    job = one(ctx.conn, m.jobs, None, m.jobs.c.id == job_id, m.jobs.c.tenant_id == ctx.tenant_id)
    if not job or job["kind"] != "report":
        fail(409, "RECONCILIATION_REQUIRED", "寄送未知狀態須先對帳，不能直接重送。")
    ctx.batch(owned(ctx, m.report_jobs, job["resource_id"])["batch_id"])

    def run():
        if job["status"] not in {"failed", "dead_letter"}:
            fail(409, "JOB_NOT_RETRYABLE", "此任務不能重試。")
        change(ctx.conn, m.jobs, ctx.tenant_id, job_id, status="queued", attempts=0, error_code=None, available_at=m.now())
        ctx.audit("job.retry", job_id)
        return {"id": job_id, "status": "queued"}
    return idempotent(ctx, request, f"job.retry:{job_id}", {}, run)


class SimEvent(Input):
    event_type: str = Field(pattern="^(clicked_candidate|human_interaction|reported)$")


def tracking_record(conn, token):
    row = one(conn, m.jobs, None, m.jobs.c.id == token, m.jobs.c.kind == "tracking_lookup", m.jobs.c.status == "active")
    if not row:
        fail(404, "TRACKING_NOT_FOUND", "教育活動連結無效。")
    set_tenant(conn, row["tenant_id"], mutation=True)
    message = one(conn, m.message_plans, row["tenant_id"], m.message_plans.c.id == row["resource_id"], m.message_plans.c.tracking_hash == digest(token))
    campaign = one(conn, m.campaigns, row["tenant_id"], m.campaigns.c.id == message["campaign_id"]) if message else None
    if not campaign or campaign["status"] not in {"observing", "scheduled"}:
        fail(410, "TRACKING_EXPIRED", "此活動觀測已關閉。")
    return row, message, campaign


@app.get("/sim/{token}/education", response_class=HTMLResponse)
def education(token: str, request: Request, conn=Depends(get_connection)):
    rate_limit(request, "sim", 60)
    tracking_record(conn, token)
    return HTMLResponse("""<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>KUANGUARD 教育練習</title><body><main><h1>先停一下，確認再操作。</h1><p>這是已授權的郵件辨識教育頁。遇到要求登入、付款或提供資料的郵件，請透過原本已知的聯絡管道確認。</p><p>本頁不接收密碼、驗證碼或個人資料。</p></main></body></html>""",
                        headers={"Content-Security-Policy": "default-src 'none'; style-src 'none'; form-action 'none'; frame-ancestors 'none'", "Cache-Control": "no-store"})


@app.post("/sim/{token}/events")
def sim_event(token: str, payload: SimEvent, request: Request, conn=Depends(get_connection)):
    rate_limit(request, "sim-events", 60)
    mapping, message, campaign = tracking_record(conn, token)
    event_type = payload.event_type
    # A public request alone does not prove human intent, even when its label says human_interaction.
    classification = "reported_by_token_holder" if event_type == "reported" else "unverified_candidate"
    event_id = request.headers.get("idempotency-key", "")
    if not event_id or len(event_id) > 128:
        fail(400, "IDEMPOTENCY_REQUIRED", "需要事件識別碼。")
    key = f"sim:{message['id']}:{event_id}"
    previous = one(conn, m.raw_events, mapping["tenant_id"], m.raw_events.c.provider_event_id == key)
    if previous:
        if previous["event_type"] != event_type:
            fail(409, "EVENT_CONFLICT", "事件識別碼已用於其他內容。")
        return {"status": "recorded", "duplicate": True}
    add(conn, m.raw_events, mapping["tenant_id"], campaign_id=campaign["id"], message_id=message["id"], event_type=event_type,
        provider_event_id=key, occurred_at=m.now(), classification=classification)
    return {"status": "recorded", "classification": classification}


@app.get("/public/certificates/{code}")
def certificate_verify(code: str, conn=Depends(get_connection)):
    route = one(conn, m.jobs, None, m.jobs.c.id == code, m.jobs.c.kind == "certificate_lookup", m.jobs.c.status == "active")
    if not route:
        fail(404, "CERTIFICATE_NOT_FOUND", "查無有效證明。")
    set_tenant(conn, route["tenant_id"])
    row = one(conn, m.certificates, route["tenant_id"], m.certificates.c.id == route["resource_id"], m.certificates.c.verification_hash == digest(code))
    if not row:
        fail(404, "CERTIFICATE_NOT_FOUND", "查無有效證明。")
    return {"valid": True, "course_title": row["course_title"], "issued_at": row["issued_at"], "personal_details": "withheld"}


# Portfolio router is included explicitly once its additive migration is installed.
