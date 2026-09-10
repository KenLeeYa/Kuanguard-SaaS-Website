from dataclasses import dataclass
from datetime import timedelta
import hashlib
import hmac
import json
import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_

from . import models as m
from .config import settings
from .db import add, all_rows, get_connection, one, set_tenant


def digest(value):
    if not isinstance(value, bytes):
        value = str(value).encode()
    return hashlib.sha256(value).hexdigest()


def fail(status, code, message):
    raise HTTPException(status, {"code": code, "message": message})


@dataclass
class Context:
    conn: object
    tenant_id: str
    user_id: str
    user: dict
    tenant: dict
    roles: set
    csrf_token: str
    trace_id: str
    delegated_projects: list | None = None
    partner_id: str | None = None
    partner_grant_id: str | None = None
    ip_hash: str | None = None
    user_agent: str = ""
    mutation: bool = False

    def require(self, *roles):
        if not self.roles.intersection(roles):
            fail(403, "ROLE_DENIED", "您的角色沒有這項操作權限。")

    def project_ids(self):
        if self.delegated_projects is not None:
            return self.delegated_projects
        return [g["resource_id"] for g in all_rows(self.conn, m.grants, self.tenant_id,
                m.grants.c.user_id == self.user_id, m.grants.c.scope == "project",
                or_(m.grants.c.expires_at.is_(None), m.grants.c.expires_at > m.now()))]

    def project(self, project_id):
        if project_id not in self.project_ids():
            fail(404, "RESOURCE_NOT_FOUND", "找不到可存取的專案。")
        row = one(self.conn, m.projects, self.tenant_id, m.projects.c.id == project_id)
        if not row:
            fail(404, "RESOURCE_NOT_FOUND", "找不到可存取的專案。")
        return row

    def batch(self, batch_id):
        row = one(self.conn, m.batches, self.tenant_id, m.batches.c.id == batch_id)
        if not row:
            fail(404, "RESOURCE_NOT_FOUND", "找不到可存取的服務批次。")
        self.project(row["project_id"])
        if self.mutation:
            from .partner import service_feature
            service_feature(self.conn, self.tenant_id, row["service_code"])
        return row

    def audit(self, action, resource_id, summary="", details=None):
        event = add(self.conn, m.audit_events, self.tenant_id, actor_id=self.user_id, action=action,
                   resource_id=resource_id, trace_id=self.trace_id, summary=summary[:1000])
        if self.ip_hash is not None:
            from . import partner_models as p
            add(self.conn, p.audit_contexts, self.tenant_id, audit_event_id=event["id"],
                partner_id=self.partner_id, roles=sorted(self.roles), ip_hash=self.ip_hash,
                user_agent=self.user_agent, details=jsonable_encoder(details or {}))
        return event


def context(request: Request, conn=Depends(get_connection)):
    from . import partner, partner_models as p
    token = request.cookies.get("kg_session", "")
    session = one(conn, m.sessions, None, m.sessions.c.token_hash == digest(token),
                  m.sessions.c.revoked.is_(False), m.sessions.c.expires_at > m.now()) if token else None
    if not session:
        fail(401, "LOGIN_REQUIRED", "請先登入。")
    mutation = request.method not in {"GET", "HEAD", "OPTIONS"}
    proof = one(conn, p.session_contexts, None, p.session_contexts.c.session_id == session["id"])
    origin = request.headers.get("origin")
    if origin:
        from urllib.parse import urlsplit
        host = partner.host_name(request.headers.get("host", ""))
        fixture_origin = settings().app_env in {"development", "test"} and host == "testserver" and origin in settings().origins
        if urlsplit(origin).hostname != host and not fixture_origin:
            fail(403, "SESSION_ORIGIN_MISMATCH", "登入資料只能由相同網域的工作空間使用。")
    lock_ids = {session["tenant_id"]}
    if proof and proof["partner_id"]:
        lock_ids.add(proof["partner_id"])
    if request.url.path.startswith("/platform/organizations/") and request.path_params.get("tenant_id"):
        lock_ids.add(request.path_params["tenant_id"])
    # Cross-wallet allocation and revocation use the same canonical lock order.
    if request.url.path.endswith("/credits") and request.url.path.startswith("/partner/customers/"):
        customer_id = request.path_params.get("customer_id")
        if customer_id and partner.link_for(conn, session["tenant_id"], customer_id):
            lock_ids.add(customer_id)
    if mutation:
        for tenant_id in sorted(lock_ids):
            set_tenant(conn, tenant_id, True)
    set_tenant(conn, session["tenant_id"], mutation)
    if mutation:
        # A revocation may have committed while this request waited for the tenant lock.
        session = one(conn, m.sessions, None, m.sessions.c.id == session["id"],
                      m.sessions.c.revoked.is_(False), m.sessions.c.expires_at > m.now())
        if not session:
            fail(401, "ACCESS_REVOKED", "操作授權已失效。")
    user = one(conn, m.users, None, m.users.c.id == session["user_id"], m.users.c.active.is_(True))
    tenant = one(conn, m.tenants, None, m.tenants.c.id == session["tenant_id"])
    roles = all_rows(conn, m.memberships, None, m.memberships.c.user_id == session["user_id"],
                     m.memberships.c.tenant_id == session["tenant_id"], m.memberships.c.active.is_(True))
    delegated_roles, delegated_projects, grant = partner.scoped_session(conn, session, request, proof)
    effective_roles = delegated_roles if delegated_roles is not None else {row["role"] for row in roles}
    if request.url.path.startswith("/partner/workspace/") and not grant:
        fail(403, "DELEGATION_REQUIRED", "請先選擇已授權的客戶工作空間。")
    if not user or not tenant or not effective_roles:
        fail(401, "ACCESS_REVOKED", "帳戶或企業授權已失效。")
    if tenant["status"] != "active":
        read_or_settle = request.method in {"GET", "HEAD", "OPTIONS"} or request.url.path.startswith(("/internal/lifecycle/", "/internal/billing/"))
        if not (tenant["status"] == "offboarding" and request.url.path.startswith("/internal/") and read_or_settle
                and {"pm", "finance"}.issubset({row["role"] for row in roles})):
            fail(401, "ACCESS_REVOKED", "企業已退場；僅授權人員可讀取保留資料與結清帳務。")
    if mutation:
        origin = request.headers.get("origin", "").rstrip("/")
        if not partner.valid_origin(conn, origin):
            fail(403, "ORIGIN_DENIED", "操作來源未獲允許。")
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), session["csrf_token"]):
            fail(403, "CSRF_DENIED", "操作驗證已失效，請重新整理頁面。")
        set_tenant(conn, session["tenant_id"])
        if request.url.path.startswith(("/customer/campaign", "/customer/recipient")):
            partner.service_feature(conn, session["tenant_id"], "SE")
        if request.url.path.startswith(("/customer/training", "/customer/enrollments")):
            partner.service_feature(conn, session["tenant_id"], "LMS")
    return Context(conn, session["tenant_id"], user["id"], user, tenant,
                   effective_roles, session["csrf_token"], request.state.trace_id, delegated_projects,
                   proof["partner_id"] if proof else None, grant["id"] if grant else None,
                   digest(request.client.host) if request.client else None, request.headers.get("user-agent", "")[:300], mutation)


def create_session(conn, user_id, tenant_id, response, host=None, partner_id=None, delegated=False):
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    add(conn, m.sessions, token_hash=digest(token), tenant_id=tenant_id, user_id=user_id,
        csrf_token=csrf, expires_at=m.now() + timedelta(hours=settings().session_hours))
    if host:
        from .partner import bind_session
        bind_session(conn, token, host, partner_id, delegated)
    secure = settings().app_env == "production" or bool(host and host.split(":")[0] not in {"testserver", "localhost", "127.0.0.1"})
    response.set_cookie("kg_session", token, httponly=True, secure=secure,
                        samesite="lax", path="/", max_age=settings().session_hours * 3600)
    return csrf


def idempotent(ctx, request, operation, payload, action):
    key = request.headers.get("idempotency-key", "")
    if not key or len(key) > 128:
        fail(400, "IDEMPOTENCY_REQUIRED", "操作需要有效的 Idempotency-Key。")
    payload_hash = digest(json.dumps(jsonable_encoder(payload), sort_keys=True, ensure_ascii=False))
    previous = one(ctx.conn, m.idempotency, ctx.tenant_id, m.idempotency.c.actor_id == ctx.user_id,
                   m.idempotency.c.operation == operation, m.idempotency.c.key == key)
    if previous:
        if previous["payload_hash"] != payload_hash:
            fail(409, "IDEMPOTENCY_CONFLICT", "相同操作識別碼不能用於不同內容。")
        return previous["response"]
    result = jsonable_encoder(action())
    add(ctx.conn, m.idempotency, ctx.tenant_id, actor_id=ctx.user_id, operation=operation,
        key=key, payload_hash=payload_hash, response=result)
    return result


def paged(items, page=1, page_size=25):
    return {"items": items[(page - 1) * page_size:page * page_size], "total": len(items), "page": page, "page_size": page_size}


def owned(ctx, table, resource_id):
    row = one(ctx.conn, table, ctx.tenant_id, table.c.id == resource_id)
    if not row:
        fail(404, "RESOURCE_NOT_FOUND", "找不到可存取的資料。")
    return row
