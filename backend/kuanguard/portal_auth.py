"""Central authentication broker with a one-use, destination-browser-bound handoff."""
from datetime import timedelta
import hmac
import secrets
from typing import Literal
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import Field
from sqlalchemy import select

from . import models as m, partner_models as p
from .config import settings
from .db import add, all_rows, aware, change, get_connection, one, set_tenant
from .partner import active_partner, base_host, host_name, link_for, require_feature, resolve_partner, valid_origin
from .project_routes import Input
from .security import create_session, digest, fail

router = APIRouter()
RETURN_PATHS = {"/partner", "/dashboard", "/learn", "/admin/overview", "/admin/platform", "/merchant"}


def central_request(request):
    host = host_name(request.headers.get("host", ""))
    config = settings()
    if host != urlsplit(config.central_auth_url).hostname and not (
        config.app_env in {"development", "test"} and host in {"testserver", "localhost", "127.0.0.1"}
    ):
        fail(403, "CENTRAL_AUTH_REQUIRED", "請由中央驗證入口登入。")


def intent_row(conn, token):
    row = one(conn, p.portal_login_intents, None, p.portal_login_intents.c.token_hash == digest(token),
              p.portal_login_intents.c.expires_at > m.now(), p.portal_login_intents.c.consumed_at.is_(None))
    if not row:
        fail(403, "LOGIN_INTENT_EXPIRED", "登入請求已失效，請由原入口重新登入。")
    return row


class PortalStart(Input):
    partner_slug: str | None = Field(default=None, max_length=80)
    tenant_id: str | None = Field(default=None, max_length=36)
    return_path: Literal["/partner", "/dashboard", "/learn", "/admin/overview", "/admin/platform", "/merchant"] = "/partner"


@router.post("/auth/portal/start")
def portal_start(payload: PortalStart, request: Request, response: Response, conn=Depends(get_connection)):
    from .api import rate_limit
    rate_limit(request, "portal-start", 20)
    origin = request.headers.get("origin", "")
    host = host_name(request.headers.get("host", ""))
    if not valid_origin(conn, origin) or urlsplit(origin).hostname != host:
        fail(403, "ORIGIN_DENIED", "請從目標平台的同源入口開始登入。")
    partner = resolve_partner(conn, host, payload.partner_slug)
    if partner:
        require_feature(conn, partner["tenant_id"], "partner_portal")
    if payload.return_path == "/partner" and not partner:
        fail(422, "PARTNER_REQUIRED", "請選擇合作夥伴入口。")
    if partner and payload.return_path.startswith("/admin"):
        fail(403, "DESTINATION_DENIED", "Partner 入口不可要求平台管理員工作階段。")
    tenant_id = payload.tenant_id or (partner["tenant_id"] if payload.return_path == "/partner" else None)
    token, binding = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    add(conn, p.portal_login_intents, token_hash=digest(token), partner_id=partner["tenant_id"] if partner else None,
        tenant_id=tenant_id, destination_origin=origin, return_path=payload.return_path,
        browser_hash=digest(binding), expires_at=m.now() + timedelta(minutes=5))
    response.set_cookie("kg_portal_binding", binding, httponly=True, secure=origin.startswith("https:"),
                        samesite="lax", max_age=300, path="/")
    central = origin if settings().app_env in {"development", "test"} and base_host(host) else settings().central_auth_url
    return {"login_url": central + "/login/continue?" + urlencode({"intent": token}), "expires_in": 300}


def eligible_tenants(conn, intent, user_id):
    memberships = all_rows(conn, m.memberships, None, m.memberships.c.user_id == user_id, m.memberships.c.active.is_(True))
    result = []
    for tenant_id in sorted({row["tenant_id"] for row in memberships}):
        if intent["tenant_id"] and tenant_id != intent["tenant_id"]:
            continue
        tenant = one(conn, m.tenants, None, m.tenants.c.id == tenant_id, m.tenants.c.status == "active")
        if not tenant:
            continue
        if intent["partner_id"]:
            active_partner(conn, intent["partner_id"])
            require_feature(conn, intent["partner_id"], "partner_portal")
            if tenant_id != intent["partner_id"] and not link_for(conn, intent["partner_id"], tenant_id):
                continue
        roles = {row["role"] for row in memberships if row["tenant_id"] == tenant_id}
        if intent["return_path"] == "/partner" and not any(role.startswith("partner_") for role in roles):
            continue
        if intent["return_path"] == "/admin/platform" and not one(conn, p.platform_memberships, None,
                p.platform_memberships.c.user_id == user_id, p.platform_memberships.c.active.is_(True)):
            continue
        result.append((tenant_id, roles))
    return result


def finish_identity(conn, intent, user_id):
    eligible = eligible_tenants(conn, intent, user_id)
    if len(eligible) != 1:
        fail(403 if not eligible else 409, "EXPLICIT_TENANT_REQUIRED", "請使用獲授權的企業入口；多企業身分須指定企業識別碼。")
    tenant_id, _ = eligible[0]
    code = secrets.token_urlsafe(40)
    claimed = conn.execute(p.portal_login_intents.update().where(p.portal_login_intents.c.id == intent["id"],
        p.portal_login_intents.c.authenticated_at.is_(None), p.portal_login_intents.c.expires_at > m.now()).values(
            user_id=user_id, tenant_id=tenant_id, authenticated_at=m.now(), code_hash=digest(code),
            expires_at=m.now() + timedelta(seconds=60)))
    if claimed.rowcount != 1:
        fail(409, "LOGIN_ALREADY_USED", "此登入請求已使用。")
    return intent["destination_origin"] + "/api/auth/portal/callback?" + urlencode({"code": code})


class DevComplete(Input):
    intent: str = Field(min_length=20, max_length=120)
    profile_key: str = Field(max_length=80)


@router.post("/auth/portal/dev-complete")
def dev_complete(payload: DevComplete, request: Request, conn=Depends(get_connection)):
    from .api import rate_limit
    from .seed import PROFILES, fixed
    from .partner_setup import PARTNER_PROFILES
    config = settings()
    if config.app_env not in {"development", "test"} or config.auth_provider != "development":
        fail(404, "NOT_FOUND", "開發登入未啟用。")
    central_request(request)
    rate_limit(request, "portal-login", 60)
    if request.headers.get("origin", "") not in config.origins | {config.central_auth_url}:
        fail(403, "ORIGIN_DENIED", "登入來源未获允許。")
    if payload.profile_key not in PROFILES | PARTNER_PROFILES:
        fail(403, "PROFILE_NOT_FOUND", "無效的示範身分。")
    user = one(conn, m.users, None, m.users.c.id == fixed(payload.profile_key), m.users.c.active.is_(True))
    if not user:
        fail(403, "PROFILE_NOT_FOUND", "此示範身分尚未建立。")
    return {"redirect": finish_identity(conn, intent_row(conn, payload.intent), user["id"])}


@router.get("/auth/portal/callback")
def portal_callback(code: str, request: Request, conn=Depends(get_connection)):
    result = conn.execute(select(p.portal_login_intents).where(p.portal_login_intents.c.code_hash == digest(code)).with_for_update()).mappings().first()
    intent = dict(result) if result else None
    if not intent or intent["consumed_at"] or aware(intent["expires_at"]) <= m.now() or not intent["authenticated_at"]:
        fail(403, "HANDOFF_EXPIRED", "登入交換碼已使用或過期。")
    host = host_name(request.headers.get("host", ""))
    if host != urlsplit(intent["destination_origin"]).hostname or not valid_origin(conn, intent["destination_origin"]):
        fail(403, "HANDOFF_DESTINATION_MISMATCH", "登入目的地不符。")
    if not hmac.compare_digest(digest(request.cookies.get("kg_portal_binding", "")), intent["browser_hash"]):
        fail(403, "HANDOFF_BROWSER_MISMATCH", "請使用發起登入的同一個瀏覽器。")
    user = one(conn, m.users, None, m.users.c.id == intent["user_id"], m.users.c.active.is_(True))
    if not user or len(eligible_tenants(conn, intent, user["id"])) != 1:
        fail(403, "ACCESS_REVOKED", "登入期間企業授權已變更。")
    consumed = conn.execute(p.portal_login_intents.update().where(p.portal_login_intents.c.id == intent["id"],
        p.portal_login_intents.c.consumed_at.is_(None)).values(consumed_at=m.now()))
    if consumed.rowcount != 1:
        fail(409, "HANDOFF_ALREADY_USED", "登入交換碼已使用。")
    previous = one(conn, m.sessions, None, m.sessions.c.token_hash == digest(request.cookies.get("kg_session", "")))
    if previous:
        change(conn, m.sessions, None, previous["id"], revoked=True)
    response = RedirectResponse(intent["return_path"], status_code=303)
    create_session(conn, user["id"], intent["tenant_id"], response, host, intent["partner_id"])
    response.delete_cookie("kg_portal_binding", path="/")
    set_tenant(conn, intent["tenant_id"])
    add(conn, m.audit_events, intent["tenant_id"], actor_id=user["id"], action="auth.portal.login",
        resource_id=intent["id"], trace_id=request.state.trace_id, summary="Host-bound one-use handoff")
    return response
