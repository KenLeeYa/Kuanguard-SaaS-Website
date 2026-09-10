"""Tenant questionnaires, personal notifications and auditable ticket status changes."""
from datetime import datetime
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select

from . import models as m
from .db import add, all_rows, aware, change, one
from .security import Context, context, digest, fail, idempotent, owned

router = APIRouter(tags=["operations"])
NOTICE = "供應商問卷與人工文字覆核；證據參照未自動查驗，不構成認證或檢測結論。"
TICKET_ROLES = ("customer_contact", "customer_admin", "campaign_manager", "training_manager", "billing_manager", "learner")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class QuestionnaireInput(Input):
    title: str = Field(min_length=1, max_length=120)
    supplier: str = Field(min_length=1, max_length=120)
    due_at: datetime
    questions: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(min_length=1, max_length=100)

    @field_validator("due_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("due_at requires an explicit timezone")
        return value


class AnswerInput(Input):
    answer: str = Field(min_length=1, max_length=10000)
    evidence_reference: str = Field(default="", max_length=2000)
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class ReviewInput(Input):
    decision: Literal["reviewed", "needs_revision", "insufficient_evidence"]
    reason: str = Field(min_length=1, max_length=1000)
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class TicketStatusInput(Input):
    status: Literal["open", "in_progress", "closed"]
    expected_status: Literal["open", "in_progress", "closed"]
    reason: str = Field(min_length=1, max_length=1000)


class TicketMessageInput(Input):
    text: str = Field(min_length=1, max_length=5000)
    visibility: Literal["customer", "internal"] = "customer"


def _query(request, paginated=False):
    if set(request.query_params) - ({"page", "page_size"} if paginated else set()):
        fail(422, "QUERY_SCOPE_FORBIDDEN", "範圍由登入角色及目前企業授權決定，不能自行指定。")


def _page(ctx, table, page, page_size, *conditions):
    conditions = (table.c.tenant_id == ctx.tenant_id, *conditions)
    total = ctx.conn.execute(select(func.count()).select_from(table).where(*conditions)).scalar_one()
    rows = [dict(row) for row in ctx.conn.execute(select(table).where(*conditions)
            .order_by(table.c.created_at.desc(), table.c.id).offset((page-1)*page_size).limit(page_size)).mappings()]
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


def _audit(ctx, action, resource_id, details):
    add(ctx.conn, m.audit_events, ctx.tenant_id, actor_id=ctx.user_id, action=action,
        resource_id=resource_id, trace_id=ctx.trace_id, summary=json.dumps(details, ensure_ascii=False, sort_keys=True))


def _questionnaire_view(row):
    return {key: row[key] for key in ("id", "title", "supplier", "due_at", "status", "created_at")} | {
        "overdue": bool(row["due_at"] and aware(row["due_at"]) < m.now() and row["status"] != "reviewed")}


def _answer_view(row):
    view = {key: row[key] for key in ("id", "questionnaire_id", "question", "review_status")}
    view.update(answer=row["answer"] or "", evidence_reference=row["evidence_reference"] or "")
    view["revision"] = digest(json.dumps(view, ensure_ascii=False, sort_keys=True))
    return view


def _answer(ctx, questionnaire_id, answer_id):
    owned(ctx, m.questionnaires, questionnaire_id)
    row = owned(ctx, m.questionnaire_answers, answer_id)
    if row["questionnaire_id"] != questionnaire_id:
        fail(404, "ANSWER_NOT_FOUND", "題目不屬於這份問卷。")
    return row


def _change_answer(ctx, row, **values):
    changed = ctx.conn.execute(m.questionnaire_answers.update().where(
        m.questionnaire_answers.c.id == row["id"], m.questionnaire_answers.c.tenant_id == ctx.tenant_id,
        *(m.questionnaire_answers.c[key] == row[key] for key in ("question", "answer", "evidence_reference", "review_status")))
        .values(**values)).rowcount
    if changed != 1:
        fail(409, "ANSWER_REVISION_CHANGED", "答案已更新，請重新閱讀目前內容。")


def _questionnaire_detail(ctx, questionnaire_id):
    row = owned(ctx, m.questionnaires, questionnaire_id)
    answers = [dict(answer) for answer in ctx.conn.execute(select(m.questionnaire_answers).where(
        m.questionnaire_answers.c.tenant_id == ctx.tenant_id,
        m.questionnaire_answers.c.questionnaire_id == questionnaire_id)
        .order_by(m.questionnaire_answers.c.created_at, m.questionnaire_answers.c.id).limit(101)).mappings()]
    if len(answers) > 100:
        fail(409, "QUESTIONNAIRE_LIMIT", "此問卷超過目前支援的 100 題，需由管理者分批處理。")
    return {**_questionnaire_view(row), "answers": [_answer_view(answer) for answer in answers],
            "scope": "current_tenant", "notice": NOTICE}


def _refresh_questionnaire_status(ctx, questionnaire_id):
    rows = all_rows(ctx.conn, m.questionnaire_answers, ctx.tenant_id,
                    m.questionnaire_answers.c.questionnaire_id == questionnaire_id)
    status = "reviewed" if rows and all(row["review_status"] == "reviewed" for row in rows) else "in_review"
    change(ctx.conn, m.questionnaires, ctx.tenant_id, questionnaire_id, status=status)


@router.get("/customer/questionnaires")
def customer_questionnaires(request: Request, ctx: Context = Depends(context), page: int = Query(1, ge=1),
                            page_size: int = Query(25, ge=1, le=100)):
    ctx.require("customer_admin")
    _query(request, True)
    result = _page(ctx, m.questionnaires, page, page_size)
    result["items"] = [_questionnaire_view(row) for row in result["items"]]
    return {**result, "scope": "current_tenant", "notice": NOTICE}


@router.post("/customer/questionnaires")
def create_questionnaire(payload: QuestionnaireInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("customer_admin")
    _query(request)

    def create():
        row = add(ctx.conn, m.questionnaires, ctx.tenant_id, **payload.model_dump(exclude={"questions"}))
        for question in payload.questions:
            add(ctx.conn, m.questionnaire_answers, ctx.tenant_id, questionnaire_id=row["id"], question=question)
        _audit(ctx, "questionnaire.create", row["id"], {"scope": "current_tenant", "question_count": len(payload.questions)})
        return {"id": row["id"]}

    receipt = idempotent(ctx, request, "questionnaire.create", payload.model_dump(), create)
    return _questionnaire_detail(ctx, receipt["id"])


@router.get("/customer/questionnaires/{questionnaire_id}")
def customer_questionnaire(questionnaire_id: str, request: Request, ctx: Context = Depends(context)):
    ctx.require("customer_admin")
    _query(request)
    return _questionnaire_detail(ctx, questionnaire_id)


@router.post("/customer/questionnaires/{questionnaire_id}/answers/{answer_id}")
def answer_question(questionnaire_id: str, answer_id: str, payload: AnswerInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("customer_admin")
    _query(request)
    row = _answer(ctx, questionnaire_id, answer_id)

    def answer():
        if payload.expected_revision != _answer_view(row)["revision"]:
            fail(409, "ANSWER_REVISION_CHANGED", "答案已更新，請重新閱讀目前內容。")
        _change_answer(ctx, row, answer=payload.answer, evidence_reference=payload.evidence_reference, review_status="unreviewed")
        _refresh_questionnaire_status(ctx, questionnaire_id)
        current = _answer(ctx, questionnaire_id, answer_id)
        _audit(ctx, "questionnaire.answer", answer_id, {"questionnaire_id": questionnaire_id,
               "previous_revision": payload.expected_revision, "revision": _answer_view(current)["revision"]})
        return {"id": answer_id}

    idempotent(ctx, request, f"questionnaire.answer:{answer_id}", payload.model_dump(), answer)
    return _questionnaire_detail(ctx, questionnaire_id)


@router.get("/internal/questionnaires")
def internal_questionnaires(request: Request, ctx: Context = Depends(context), page: int = Query(1, ge=1),
                            page_size: int = Query(25, ge=1, le=100)):
    ctx.require("reviewer")
    _query(request, True)
    result = _page(ctx, m.questionnaires, page, page_size)
    result["items"] = [_questionnaire_view(row) for row in result["items"]]
    return {**result, "scope": "current_tenant", "notice": NOTICE}


@router.get("/internal/questionnaires/{questionnaire_id}")
def internal_questionnaire(questionnaire_id: str, request: Request, ctx: Context = Depends(context)):
    ctx.require("reviewer")
    _query(request)
    return _questionnaire_detail(ctx, questionnaire_id)


@router.post("/internal/questionnaires/{questionnaire_id}/answers/{answer_id}/review")
def review_answer(questionnaire_id: str, answer_id: str, payload: ReviewInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("reviewer")
    _query(request)
    row = _answer(ctx, questionnaire_id, answer_id)

    def review():
        if payload.expected_revision != _answer_view(row)["revision"]:
            fail(409, "ANSWER_REVISION_CHANGED", "答案或覆核狀態已改變，請重新檢查。")
        if payload.decision == "reviewed" and (not row["answer"] or not row["evidence_reference"]):
            fail(409, "QUESTIONNAIRE_EVIDENCE_REQUIRED", "缺少文字答案或證據參照，請標示資料不足或要求補充。")
        _change_answer(ctx, row, review_status=payload.decision)
        _refresh_questionnaire_status(ctx, questionnaire_id)
        _audit(ctx, "questionnaire.review", answer_id, {"questionnaire_id": questionnaire_id,
               "reviewed_revision": payload.expected_revision, "decision": payload.decision, "reason": payload.reason})
        return {"id": answer_id}

    idempotent(ctx, request, f"questionnaire.review:{answer_id}", payload.model_dump(), review)
    return _questionnaire_detail(ctx, questionnaire_id)


def _notification_view(row):
    return {key: row[key] for key in ("id", "title", "text", "created_at", "read_at")} | {"is_read": row["read_at"] is not None}


@router.get("/customer/notifications")
def notifications(request: Request, ctx: Context = Depends(context), page: int = Query(1, ge=1),
                  page_size: int = Query(25, ge=1, le=100)):
    _query(request, True)
    result = _page(ctx, m.notifications, page, page_size, m.notifications.c.user_id == ctx.user_id)
    result["items"] = [_notification_view(row) for row in result["items"]]
    return result


@router.post("/customer/notifications/{notification_id}/read")
def read_notification(notification_id: str, request: Request, payload: Input | None = None, ctx: Context = Depends(context)):
    _query(request)
    row = one(ctx.conn, m.notifications, ctx.tenant_id, m.notifications.c.id == notification_id,
              m.notifications.c.user_id == ctx.user_id)
    if not row:
        fail(404, "NOTIFICATION_NOT_FOUND", "找不到您的通知。")

    def mark():
        ctx.conn.execute(m.notifications.update().where(m.notifications.c.tenant_id == ctx.tenant_id,
            m.notifications.c.id == notification_id, m.notifications.c.user_id == ctx.user_id,
            m.notifications.c.read_at.is_(None)).values(read_at=m.now()))
        return {"id": notification_id}

    idempotent(ctx, request, f"notification.read:{notification_id}", {}, mark)
    return _notification_view(owned(ctx, m.notifications, notification_id))


def _ticket_view(row, internal=False):
    view = {key: row[key] for key in ("id", "subject", "text", "status", "created_at")}
    if internal:
        view["actor_id"] = row["actor_id"]
    return view


def _ticket_detail(ctx, row, internal=False):
    conditions = [] if internal else [m.ticket_messages.c.visibility == "customer"]
    messages = all_rows(ctx.conn, m.ticket_messages, ctx.tenant_id,
                        m.ticket_messages.c.ticket_id == row["id"], *conditions)
    return {**_ticket_view(row, internal), "messages": [
        {key: message[key] for key in ("id", "text", "visibility", "created_at")} |
        {"from_support": message["actor_id"] != row["actor_id"]} for message in messages]}


def _send_ticket_message(ctx, request, row, payload, internal=False):
    if not internal and payload.visibility != "customer":
        fail(403, "INTERNAL_NOTE_DENIED", "客戶工單不能寫入內部備註。")

    def send():
        if row["status"] == "closed":
            fail(409, "TICKET_CLOSED", "工單已關閉，請由負責人重新開啟後再回覆。")
        message = add(ctx.conn, m.ticket_messages, ctx.tenant_id, ticket_id=row["id"],
                      actor_id=ctx.user_id, **payload.model_dump())
        if internal and payload.visibility == "customer" and row["actor_id"] != ctx.user_id:
            add(ctx.conn, m.notifications, ctx.tenant_id, user_id=row["actor_id"],
                title="工單已有回覆", text="請至平台開啟您的工單查看回覆。")
        ctx.audit("ticket.reply", row["id"], f"message={message['id']}; visibility={payload.visibility}")
        return {"id": message["id"]}

    idempotent(ctx, request, f"ticket.reply:{row['id']}", payload.model_dump(), send)
    return _ticket_detail(ctx, row, internal)


@router.get("/customer/tickets/{ticket_id}")
def customer_ticket(ticket_id: str, request: Request, ctx: Context = Depends(context)):
    ctx.require(*TICKET_ROLES)
    _query(request)
    row = one(ctx.conn, m.tickets, ctx.tenant_id, m.tickets.c.id == ticket_id, m.tickets.c.actor_id == ctx.user_id)
    if not row:
        fail(404, "TICKET_NOT_FOUND", "找不到您的工單。")
    return _ticket_detail(ctx, row)


@router.post("/customer/tickets/{ticket_id}/messages")
def customer_ticket_message(ticket_id: str, payload: TicketMessageInput, request: Request,
                             ctx: Context = Depends(context)):
    ctx.require(*TICKET_ROLES)
    _query(request)
    row = one(ctx.conn, m.tickets, ctx.tenant_id, m.tickets.c.id == ticket_id, m.tickets.c.actor_id == ctx.user_id)
    if not row:
        fail(404, "TICKET_NOT_FOUND", "找不到您的工單。")
    return _send_ticket_message(ctx, request, row, payload)


@router.get("/internal/tickets")
def internal_tickets(request: Request, ctx: Context = Depends(context), page: int = Query(1, ge=1),
                     page_size: int = Query(25, ge=1, le=100)):
    ctx.require("pm")
    _query(request, True)
    result = _page(ctx, m.tickets, page, page_size)
    result["items"] = [_ticket_view(row, True) for row in result["items"]]
    return result


@router.get("/internal/tickets/{ticket_id}")
def internal_ticket(ticket_id: str, request: Request, ctx: Context = Depends(context)):
    ctx.require("pm")
    _query(request)
    return _ticket_detail(ctx, owned(ctx, m.tickets, ticket_id), True)


@router.post("/internal/tickets/{ticket_id}/messages")
def internal_ticket_message(ticket_id: str, payload: TicketMessageInput, request: Request,
                             ctx: Context = Depends(context)):
    ctx.require("pm")
    _query(request)
    return _send_ticket_message(ctx, request, owned(ctx, m.tickets, ticket_id), payload, True)


@router.post("/internal/tickets/{ticket_id}/status")
def ticket_status(ticket_id: str, payload: TicketStatusInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("pm")
    _query(request)
    row = owned(ctx, m.tickets, ticket_id)

    def update():
        if row["status"] != payload.expected_status:
            fail(409, "TICKET_STATE_CHANGED", "工單狀態已改變，請重新確認。")
        changed = ctx.conn.execute(m.tickets.update().where(m.tickets.c.id == ticket_id,
            m.tickets.c.tenant_id == ctx.tenant_id, m.tickets.c.status == payload.expected_status).values(status=payload.status)).rowcount
        if changed != 1:
            fail(409, "TICKET_STATE_CHANGED", "工單狀態已改變，請重新確認。")
        _audit(ctx, "ticket.status", ticket_id, {"previous_status": row["status"], "status": payload.status, "reason": payload.reason})
        return {"id": ticket_id}

    idempotent(ctx, request, f"ticket.status:{ticket_id}", payload.model_dump(), update)
    return _ticket_view(owned(ctx, m.tickets, ticket_id), True)
