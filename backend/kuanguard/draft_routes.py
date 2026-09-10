"""Short-lived server drafts with explicit fields, actor scope and optimistic versions."""
from datetime import timedelta
import json
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field

from . import models as m
from .db import add, aware, one
from .project_routes import Input
from .security import Context, context, fail

router = APIRouter(tags=["drafts"])
KINDS = {
    "campaign": ("campaign_manager", {"name", "group_id", "scheduled_at", "remediation_course_id"}),
    "training": ("training_manager", {"course_id", "learner_id", "cohort"}),
    "purchase": ("billing_manager", {"points", "order_id"}),
}


class DraftInput(Input):
    expected_version: int = Field(ge=0, strict=True)
    payload: dict


def draft_scope(ctx, request, kind, key, delete=False):
    ctx.require(KINDS[kind][0])
    if set(request.query_params) - ({"version"} if delete else set()):
        fail(422, "DRAFT_SCOPE_FORBIDDEN", "草稿範圍由目前企業與登入身分決定。")
    if key != "new":
        fail(422, "DRAFT_KEY_INVALID", "目前每種操作保留一份未完成草稿。")
    return (m.form_drafts.c.tenant_id == ctx.tenant_id, m.form_drafts.c.actor_id == ctx.user_id,
            m.form_drafts.c.kind == kind, m.form_drafts.c.draft_key == key)


def view(row):
    return {key: row[key] for key in ("id", "version", "payload", "updated_at", "expires_at")}


@router.get("/app/drafts/{kind}/{key}")
def get_draft(kind: Literal["campaign", "training", "purchase"], key: str, request: Request,
              ctx: Context = Depends(context)):
    conditions = draft_scope(ctx, request, kind, key)
    row = one(ctx.conn, m.form_drafts, ctx.tenant_id, *conditions)
    if not row or aware(row["expires_at"]) <= m.now():
        fail(404, "DRAFT_NOT_FOUND", "尚無有效草稿。")
    return view(row)


@router.put("/app/drafts/{kind}/{key}")
def save_draft(kind: Literal["campaign", "training", "purchase"], key: str, payload: DraftInput,
               request: Request, ctx: Context = Depends(context)):
    conditions = draft_scope(ctx, request, kind, key)
    if set(payload.payload) - KINDS[kind][1] or len(json.dumps(payload.payload).encode()) > 4096:
        fail(422, "DRAFT_FIELDS_INVALID", "僅能儲存此操作的基本欄位，不接收名單、附件或證據。")
    for field, value in payload.payload.items():
        if field == "points":
            valid = type(value) is int and value in {100, 500, 1000}
        else:
            valid = value is None or isinstance(value, str) and len(value) <= (200 if field == "name" else 120)
        if not valid:
            fail(422, "DRAFT_VALUE_INVALID", "草稿欄位格式無效。")
    current = one(ctx.conn, m.form_drafts, ctx.tenant_id, *conditions)
    now = m.now()
    expired = current and aware(current["expires_at"]) <= now
    version = 0 if not current or expired else current["version"]
    if payload.expected_version != version:
        if not expired and current and version == payload.expected_version + 1 and current["payload"] == payload.payload:
            return view(current)  # Safe retry when the preceding successful response was lost.
        fail(409, "DRAFT_VERSION_CHANGED", "另一個視窗已更新草稿，請先比較目前版本。")
    values = {"version": (current["version"] + 1 if current else 1), "payload": payload.payload,
              "updated_at": now, "expires_at": now + timedelta(hours=24)}
    if current:
        changed = ctx.conn.execute(m.form_drafts.update().where(*conditions, m.form_drafts.c.version == current["version"])
                                   .values(**values)).rowcount
        if changed != 1:
            fail(409, "DRAFT_VERSION_CHANGED", "草稿已更新，請重新讀取。")
    else:
        add(ctx.conn, m.form_drafts, ctx.tenant_id, actor_id=ctx.user_id, kind=kind, draft_key=key, **values)
    return view(one(ctx.conn, m.form_drafts, ctx.tenant_id, *conditions))


@router.delete("/app/drafts/{kind}/{key}")
def delete_draft(kind: Literal["campaign", "training", "purchase"], key: str, request: Request,
                 version: int = Query(ge=1), ctx: Context = Depends(context)):
    conditions = draft_scope(ctx, request, kind, key, delete=True)
    current = one(ctx.conn, m.form_drafts, ctx.tenant_id, *conditions)
    if current:
        if current["version"] != version:
            fail(409, "DRAFT_VERSION_CHANGED", "草稿已更新，不能刪除其他視窗的新內容。")
        count = ctx.conn.execute(m.form_drafts.delete().where(*conditions, m.form_drafts.c.version == version)).rowcount
        if count != 1:
            fail(409, "DRAFT_VERSION_CHANGED", "草稿已更新，請重新讀取。")
    return {"status": "deleted"}
