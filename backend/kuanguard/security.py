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

    def require(self, *roles):
        if not self.roles.intersection(roles):
            fail(403, "ROLE_DENIED", "您的角色沒有這項操作權限。")

    def project_ids(self):
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
        return row

    def audit(self, action, resource_id, summary=""):
        return add(self.conn, m.audit_events, self.tenant_id, actor_id=self.user_id, action=action,
                   resource_id=resource_id, trace_id=self.trace_id, summary=summary[:1000])


def context(request: Request, conn=Depends(get_connection)):
    token = request.cookies.get("kg_session", "")
    session = one(conn, m.sessions, None, m.sessions.c.token_hash == digest(token),
                  m.sessions.c.revoked.is_(False), m.sessions.c.expires_at > m.now()) if token else None
    if not session:
        fail(401, "LOGIN_REQUIRED", "請先登入。")
    mutation = request.method not in {"GET", "HEAD", "OPTIONS"}
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
    if not user or not tenant or not roles:
        fail(401, "ACCESS_REVOKED", "帳戶或企業授權已失效。")
    if tenant["status"] != "active":
        read_or_settle = request.method in {"GET", "HEAD", "OPTIONS"} or request.url.path.startswith(("/internal/lifecycle/", "/internal/billing/"))
        if not (tenant["status"] == "offboarding" and request.url.path.startswith("/internal/") and read_or_settle
                and {"pm", "finance"}.issubset({row["role"] for row in roles})):
            fail(401, "ACCESS_REVOKED", "企業已退場；僅授權人員可讀取保留資料與結清帳務。")
    if mutation:
        origin = request.headers.get("origin", "").rstrip("/")
        if origin not in settings().origins:
            fail(403, "ORIGIN_DENIED", "操作來源未獲允許。")
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), session["csrf_token"]):
            fail(403, "CSRF_DENIED", "操作驗證已失效，請重新整理頁面。")
    return Context(conn, session["tenant_id"], user["id"], user, tenant,
                   {r["role"] for r in roles}, session["csrf_token"], request.state.trace_id)


def create_session(conn, user_id, tenant_id, response):
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    add(conn, m.sessions, token_hash=digest(token), tenant_id=tenant_id, user_id=user_id,
        csrf_token=csrf, expires_at=m.now() + timedelta(hours=settings().session_hours))
    response.set_cookie("kg_session", token, httponly=True, secure=settings().app_env == "production",
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
