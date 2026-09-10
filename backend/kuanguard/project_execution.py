"""Project-scoped tasks, decisions, costs and explicitly configured dispatch checks."""
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import delete, or_, text

from . import execution_models as e, models as m
from .catalog import SERVICE_CODES
from .config import settings
from .db import add, all_rows, aware, change, one, set_tenant
from .security import Context, context, fail, idempotent, owned, paged

router = APIRouter()
STAFF = ("pm", "engineer", "reviewer")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def timezone_required(value):
    if value is not None and value.tzinfo is None:
        raise ValueError("Timezone is required")
    return value.astimezone(timezone.utc) if value is not None else None


class TaskInput(Input):
    title: str = Field(min_length=1, max_length=120)
    status: Literal["open", "in_progress", "blocked", "done"] = "open"
    visibility: Literal["internal", "customer"] = "internal"
    customer_note: str = Field(default="", max_length=10000)
    internal_note: str = Field(default="", max_length=10000)
    batch_id: str | None = None
    assigned_to: str | None = None
    due_at: datetime | None = None
    dependency_ids: list[str] = Field(default_factory=list, max_length=20)

    _timezone = field_validator("due_at")(timezone_required)


class TaskUpdateInput(TaskInput):
    expected_version: int = Field(ge=1, strict=True)


class DecisionInput(Input):
    title: str = Field(min_length=1, max_length=120)
    occurred_at: datetime
    visibility: Literal["internal", "customer"] = "internal"
    customer_text: str = Field(default="", max_length=10000)
    internal_note: str = Field(default="", max_length=10000)
    batch_id: str | None = None
    publication_id: str | None = None
    task_ids: list[str] = Field(default_factory=list, max_length=20)

    _timezone = field_validator("occurred_at")(timezone_required)

    @model_validator(mode="after")
    def has_text(self):
        if not self.customer_text and not self.internal_note:
            raise ValueError("A decision must contain text")
        if self.visibility == "customer" and not self.customer_text:
            raise ValueError("Customer-visible decisions require customer_text")
        return self


class CostInput(Input):
    phase: Literal["estimated", "actual"]
    category: Literal["onsite", "travel", "analysis", "review", "retest", "tools", "cloud", "outsource", "other"]
    minutes: int = Field(ge=0, le=10_000_000, strict=True)
    cost_minor: int | None = Field(default=None, ge=0, le=2_000_000_000, strict=True)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    task_id: str | None = None
    note: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def paired_amount(self):
        if (self.cost_minor is None) != (self.currency is None):
            raise ValueError("Explicit cost and currency must be supplied together")
        return self


class ReasonInput(Input):
    reason: str = Field(min_length=1, max_length=1000)


class PolicyInput(ReasonInput):
    expected_version: int = Field(ge=0, strict=True)
    travel_buffer_minutes: int = Field(ge=0, le=1440, strict=True)


class QualificationInput(ReasonInput):
    expected_version: int = Field(ge=0, strict=True)
    user_id: str
    role: Literal["engineer", "reviewer"]
    service_code: str
    valid_until: datetime | None = None
    active: bool

    _timezone = field_validator("valid_until")(timezone_required)


class ToolInput(ReasonInput):
    expected_version: int = Field(ge=0, strict=True)
    name: str = Field(min_length=1, max_length=120)
    capacity: int = Field(ge=1, le=100, strict=True)
    service_codes: list[str] = Field(min_length=1, max_length=7)
    active: bool


def project_task(ctx, task_id, project_id):
    task = owned(ctx, m.tasks, task_id)
    if task["project_id"] != project_id:
        fail(404, "RESOURCE_NOT_FOUND", "找不到可存取的專案待辦。")
    return task


def task_views(ctx, project_id, employee=False):
    ctx.project(project_id)
    tasks = all_rows(ctx.conn, m.tasks, ctx.tenant_id, m.tasks.c.project_id == project_id)
    by_id = {row["id"]: row for row in tasks}
    details = {row["task_id"]: row for row in all_rows(ctx.conn, e.task_details, ctx.tenant_id,
               e.task_details.c.task_id.in_(by_id))}
    edges = all_rows(ctx.conn, e.task_dependencies, ctx.tenant_id, e.task_dependencies.c.task_id.in_(by_id))
    visible = {row["id"] for row in tasks if employee or row["visibility"] == "customer"}
    result = []
    for task in tasks:
        if task["id"] not in visible:
            continue
        detail = details.get(task["id"], {})
        dependencies = [edge["depends_on_id"] for edge in edges if edge["task_id"] == task["id"]]
        blocked = any(by_id.get(key, {}).get("status") != "done" for key in dependencies)
        row = {key: task[key] for key in ("id", "project_id", "batch_id", "title", "status", "due_at", "visibility")}
        row.update(customer_note=detail.get("customer_note", ""), version=detail.get("version", 1),
                   effective_status="blocked" if blocked and task["status"] != "done" else task["status"],
                   dependency_ids=[key for key in dependencies if key in visible])
        if employee:
            row.update(internal_note=detail.get("internal_note", ""), assigned_to=task["assigned_to"])
        result.append(row)
    return result


@router.get("/internal/projects/{project_id}/tasks")
def internal_tasks(project_id: str, ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    ctx.require(*STAFF)
    return paged(task_views(ctx, project_id, True), page, page_size)


@router.get("/customer/projects/{project_id}/tasks")
def customer_tasks(project_id: str, ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    ctx.require("customer_contact")
    return paged(task_views(ctx, project_id), page, page_size)


def validate_task(ctx, project_id, task_id, payload):
    tasks = all_rows(ctx.conn, m.tasks, ctx.tenant_id, m.tasks.c.project_id == project_id)
    by_id = {row["id"]: row for row in tasks}
    if task_id not in by_id and len(tasks) >= 1000:
        fail(409, "TASK_LIMIT", "單一專案最多 1000 個待辦。")
    if payload.batch_id and ctx.batch(payload.batch_id)["project_id"] != project_id:
        fail(404, "RESOURCE_NOT_FOUND", "批次不屬於此專案。")
    if payload.assigned_to:
        user = one(ctx.conn, m.users, None, m.users.c.id == payload.assigned_to, m.users.c.active.is_(True))
        membership = one(ctx.conn, m.memberships, None, m.memberships.c.tenant_id == ctx.tenant_id,
                         m.memberships.c.user_id == payload.assigned_to, m.memberships.c.active.is_(True))
        grant = one(ctx.conn, m.grants, ctx.tenant_id, m.grants.c.user_id == payload.assigned_to,
                    m.grants.c.resource_id == project_id, m.grants.c.scope == "project",
                    or_(m.grants.c.expires_at.is_(None), m.grants.c.expires_at > m.now()))
        if not user or not membership or not grant:
            fail(422, "INVALID_ASSIGNMENT", "待辦負責人須有有效帳戶及專案授權。")
    dependencies = set(payload.dependency_ids)
    if len(dependencies) != len(payload.dependency_ids):
        fail(422, "DUPLICATE_DEPENDENCY", "依賴待辦不能重複。")
    for dependency in dependencies:
        project_task(ctx, dependency, project_id)
    edges = all_rows(ctx.conn, e.task_dependencies, ctx.tenant_id, e.task_dependencies.c.task_id.in_(by_id))
    graph = {}
    for edge in edges:
        graph.setdefault(edge["task_id"], []).append(edge["depends_on_id"])
    pending, seen = list(dependencies), set()
    while pending:
        current = pending.pop()
        if current == task_id:
            fail(409, "DEPENDENCY_CYCLE", "待辦依賴不能形成循環。")
        if current not in seen:
            seen.add(current)
            pending.extend(graph.get(current, []))
    if payload.status == "done" and any(by_id[key]["status"] != "done" for key in dependencies):
        fail(409, "DEPENDENCY_BLOCKED", "前置待辦尚未完成。")
    if payload.status != "done" and any(edge["depends_on_id"] == task_id and by_id[edge["task_id"]]["status"] == "done" for edge in edges):
        fail(409, "COMPLETED_DEPENDENT", "已完成的後續待辦依賴此項；請先重開後續待辦。")
    if payload.status == "blocked" and not (payload.internal_note or payload.customer_note):
        fail(422, "BLOCK_REASON_REQUIRED", "阻擋狀態需填寫原因。")


def save_task(ctx, project_id, task_id, payload, creating):
    detail = one(ctx.conn, e.task_details, ctx.tenant_id, e.task_details.c.task_id == task_id)
    version = detail["version"] if detail else 1
    if not creating and payload.expected_version != version:
        fail(409, "STALE_VERSION", "待辦已更新，請重新整理。")
    validate_task(ctx, project_id, task_id, payload)
    values = {key: getattr(payload, key) for key in ("title", "status", "visibility", "batch_id", "assigned_to", "due_at")}
    if creating:
        add(ctx.conn, m.tasks, ctx.tenant_id, id=task_id, project_id=project_id, **values)
    else:
        change(ctx.conn, m.tasks, ctx.tenant_id, task_id, **values)
    details = {"customer_note": payload.customer_note, "internal_note": payload.internal_note,
               "version": 1 if creating else version + 1}
    if detail:
        change(ctx.conn, e.task_details, ctx.tenant_id, detail["id"], **details)
    else:
        add(ctx.conn, e.task_details, ctx.tenant_id, task_id=task_id, **details)
    ctx.conn.execute(delete(e.task_dependencies).where(e.task_dependencies.c.tenant_id == ctx.tenant_id, e.task_dependencies.c.task_id == task_id))
    for dependency in payload.dependency_ids:
        add(ctx.conn, e.task_dependencies, ctx.tenant_id, task_id=task_id, depends_on_id=dependency)
    ctx.audit("task.create" if creating else "task.update", task_id, f"version={details['version']}; visibility={payload.visibility}")
    return next(row for row in task_views(ctx, project_id, True) if row["id"] == task_id)


@router.post("/internal/projects/{project_id}/tasks")
def create_task(project_id: str, payload: TaskInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("pm")
    ctx.project(project_id)
    return idempotent(ctx, request, f"task.create:{project_id}", payload.model_dump(), lambda: save_task(ctx, project_id, m.uid(), payload, True))


@router.post("/internal/tasks/{task_id}")
def update_task(task_id: str, payload: TaskUpdateInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("pm")
    task = owned(ctx, m.tasks, task_id)
    ctx.project(task["project_id"])
    return idempotent(ctx, request, f"task.update:{task_id}", payload.model_dump(), lambda: save_task(ctx, task["project_id"], task_id, payload, False))


def decision_views(ctx, project_id, employee=False):
    ctx.project(project_id)
    visible_tasks = {row["id"] for row in task_views(ctx, project_id, employee)}
    result = []
    for row in all_rows(ctx.conn, e.meeting_decisions, ctx.tenant_id, e.meeting_decisions.c.project_id == project_id):
        if not employee and row["visibility"] != "customer":
            continue
        item = {key: row[key] for key in ("id", "project_id", "batch_id", "publication_id", "scope_version", "title", "occurred_at", "visibility", "customer_text")}
        item["task_ids"] = [key for key in row["task_ids"] if key in visible_tasks]
        if employee:
            item.update(internal_note=row["internal_note"], actor_id=row["actor_id"])
        result.append(item)
    return sorted(result, key=lambda row: (aware(row["occurred_at"]), row["id"]), reverse=True)


@router.get("/internal/projects/{project_id}/decisions")
def internal_decisions(project_id: str, ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    ctx.require(*STAFF)
    return paged(decision_views(ctx, project_id, True), page, page_size)


@router.get("/customer/projects/{project_id}/decisions")
def customer_decisions(project_id: str, ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    ctx.require("customer_contact")
    return paged(decision_views(ctx, project_id), page, page_size)


@router.post("/internal/projects/{project_id}/decisions")
def create_decision(project_id: str, payload: DecisionInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("pm")
    ctx.project(project_id)

    def run():
        batch = ctx.batch(payload.batch_id) if payload.batch_id else None
        if batch and batch["project_id"] != project_id:
            fail(404, "RESOURCE_NOT_FOUND", "批次不屬於此專案。")
        if payload.publication_id:
            publication = owned(ctx, m.publications, payload.publication_id)
            report_batch = ctx.batch(publication["batch_id"])
            if report_batch["project_id"] != project_id or (batch and batch["id"] != report_batch["id"]):
                fail(404, "RESOURCE_NOT_FOUND", "報告不屬於此專案或批次。")
        for task_id in payload.task_ids:
            project_task(ctx, task_id, project_id)
        if len(set(payload.task_ids)) != len(payload.task_ids):
            fail(422, "DUPLICATE_TASK", "決議連結待辦不能重複。")
        row = add(ctx.conn, e.meeting_decisions, ctx.tenant_id, project_id=project_id, actor_id=ctx.user_id,
                  scope_version=batch["scope_version"] if batch else None, **payload.model_dump())
        ctx.audit("decision.create", row["id"], f"visibility={payload.visibility}")
        return next(item for item in decision_views(ctx, project_id, True) if item["id"] == row["id"])
    return idempotent(ctx, request, f"decision.create:{project_id}", payload.model_dump(), run)


@router.get("/internal/cost-projects")
def cost_projects(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    ctx.require("pm", "finance")
    rows = all_rows(ctx.conn, m.projects, ctx.tenant_id, m.projects.c.id.in_(ctx.project_ids()))
    return paged([{key: row[key] for key in ("id", "name", "year")} for row in rows], page, page_size)


def margin_projection(ctx, project, totals, legacy):
    contract = one(ctx.conn, m.contracts, ctx.tenant_id, m.contracts.c.id == project["contract_id"],
                   m.contracts.c.status == "active") if project["contract_id"] else None
    quote = one(ctx.conn, m.quotes, ctx.tenant_id, m.quotes.c.id == contract["quote_id"]) if contract else None
    currency = quote["currency"] if quote else None
    amount = contract["amount_minor"] if contract else None
    contract_reason = ("no_active_contract" if not contract else "contract_quote_unavailable" if not quote else
        "contract_amount_unconfigured" if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0 else
        "contract_quote_amount_mismatch" if amount != quote["amount_minor"] else
        "contract_currency_unconfigured" if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha() or not currency.isupper() else None)
    result = {"basis": "合約金額減已登錄成本，非正式收入認列",
              "contract_amount_minor": amount if contract_reason is None else None,
              "currency": currency if contract_reason is None else None, "contract_reason": contract_reason}
    for phase, summary in totals.items():
        amounts = summary["amounts"]
        reason = (contract_reason or ("unclassified_legacy_entries" if legacy else None) or
                  ("unpriced_entries" if summary["unpriced_entries"] else None) or
                  ("cost_not_entered" if not amounts else None) or
                  ("mixed_cost_currencies" if len(amounts) != 1 else None) or
                  ("cost_currency_mismatch" if amounts and amounts[0]["currency"] != currency else None))
        cost = amounts[0]["cost_minor"] if reason is None else None
        result.update({f"{phase}_cost_minor": cost, f"{phase}_gross_margin_minor": amount - cost if reason is None else None,
                       f"{phase}_reason": reason})
    return result


@router.get("/internal/projects/{project_id}/costs")
def list_costs(project_id: str, ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    ctx.require("pm", "finance")
    project = ctx.project(project_id)
    rows = all_rows(ctx.conn, e.project_cost_entries, ctx.tenant_id, e.project_cost_entries.c.project_id == project_id)
    totals = {}
    for phase in ("estimated", "actual"):
        active = [row for row in rows if row["phase"] == phase and row["voided_at"] is None]
        currencies = sorted({row["currency"] for row in active if row["currency"]})
        totals[phase] = {"minutes": sum(row["minutes"] for row in active),
            "amounts": [{"currency": currency, "cost_minor": sum(row["cost_minor"] for row in active if row["currency"] == currency)} for currency in currencies],
            "unpriced_entries": sum(row["cost_minor"] is None for row in active),
            "cost_status": "unconfigured" if not active or any(row["cost_minor"] is None for row in active) else "entered"}
    legacy = all_rows(ctx.conn, m.time_entries, ctx.tenant_id, m.time_entries.c.project_id == project_id)
    return {**paged(rows, page, page_size), "totals": totals, "legacy_entries": legacy,
            "legacy_status": "unclassified_excluded" if legacy else "none", "pricing_policy": "explicit_entered_amounts_no_automatic_rate",
            "margin": margin_projection(ctx, project, totals, legacy)}


@router.post("/internal/projects/{project_id}/costs")
def create_cost(project_id: str, payload: CostInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("pm", "finance")
    ctx.project(project_id)

    def run():
        if payload.task_id:
            project_task(ctx, payload.task_id, project_id)
        row = add(ctx.conn, e.project_cost_entries, ctx.tenant_id, project_id=project_id, actor_id=ctx.user_id, **payload.model_dump())
        ctx.audit("project_cost.create", row["id"], f"phase={payload.phase}")
        return row
    return idempotent(ctx, request, f"project_cost.create:{project_id}", payload.model_dump(), run)


@router.post("/internal/costs/{cost_id}/void")
def void_cost(cost_id: str, payload: ReasonInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("pm", "finance")
    cost = owned(ctx, e.project_cost_entries, cost_id)
    ctx.project(cost["project_id"])

    def run():
        if cost["voided_at"] is not None:
            fail(409, "COST_ALREADY_VOID", "工時成本紀錄已作廢。")
        change(ctx.conn, e.project_cost_entries, ctx.tenant_id, cost_id, voided_at=m.now(), void_reason=payload.reason)
        ctx.audit("project_cost.void", cost_id, payload.reason)
        return owned(ctx, e.project_cost_entries, cost_id)
    return idempotent(ctx, request, f"project_cost.void:{cost_id}", payload.model_dump(), run)


def active_member(ctx, user_id, role):
    user = one(ctx.conn, m.users, None, m.users.c.id == user_id, m.users.c.active.is_(True))
    member = one(ctx.conn, m.memberships, None, m.memberships.c.tenant_id == ctx.tenant_id,
                 m.memberships.c.user_id == user_id, m.memberships.c.role == role, m.memberships.c.active.is_(True))
    if not user or not member:
        fail(422, "INVALID_ASSIGNMENT", "派工人員須有企業內的有效帳戶及角色。")


def dispatch_policy(ctx):
    row = one(ctx.conn, e.dispatch_policies, ctx.tenant_id)
    return {"status": "configured", **row} if row else {"status": "unconfigured", "version": 0, "travel_buffer_minutes": None}


def dispatch_view(ctx):
    ctx.require(*STAFF)
    members = all_rows(ctx.conn, m.memberships, None, m.memberships.c.tenant_id == ctx.tenant_id,
                       m.memberships.c.role.in_(["engineer", "reviewer"]), m.memberships.c.active.is_(True))
    qualifications = all_rows(ctx.conn, e.dispatch_qualifications, ctx.tenant_id)
    people = {}
    for member in members:
        user = one(ctx.conn, m.users, None, m.users.c.id == member["user_id"], m.users.c.active.is_(True))
        if not user:
            continue
        person = people.setdefault(user["id"], {"id": user["id"], "name": user["name"], "roles": [], "skills": [], "qualifications": []})
        person["roles"].append(member["role"])
        valid = [row for row in qualifications if row["user_id"] == user["id"] and row["role"] == member["role"] and row["active"]
                 and (row["valid_until"] is None or aware(row["valid_until"]) > m.now())]
        person["qualifications"].extend(valid)
        person["skills"] = sorted(set(person["skills"]) | {row["service_code"] for row in valid})
        person["qualification_status"] = "configured" if person["qualifications"] else "unconfigured"
    policy = dispatch_policy(ctx)
    batches = all_rows(ctx.conn, m.batches, ctx.tenant_id, m.batches.c.project_id.in_(ctx.project_ids()))
    return {**paged(list(people.values()), page_size=100), "batches": batches, "policy": policy,
            "tools": all_rows(ctx.conn, e.dispatch_tools, ctx.tenant_id),
            "travel_buffer_minutes": policy["travel_buffer_minutes"], "skills_policy": "explicit_qualification_required"}


@router.get("/internal/dispatch/policy")
def get_policy(ctx: Context = Depends(context)):
    ctx.require(*STAFF)
    return dispatch_policy(ctx)


def upsert_config(ctx, table, previous, expected_version, values):
    if expected_version != (previous["version"] if previous else 0):
        fail(409, "STALE_VERSION", "設定已更新，請重新整理。")
    if previous:
        change(ctx.conn, table, ctx.tenant_id, previous["id"], **values, version=previous["version"] + 1)
        row = owned(ctx, table, previous["id"])
    else:
        row = add(ctx.conn, table, ctx.tenant_id, **values, version=1)
    ctx.audit(f"{table.name}.configure", row["id"], values["reason"])
    return row


@router.post("/internal/dispatch/policy")
def configure_policy(payload: PolicyInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("pm")
    return idempotent(ctx, request, "dispatch.policy", payload.model_dump(), lambda: upsert_config(ctx, e.dispatch_policies,
        one(ctx.conn, e.dispatch_policies, ctx.tenant_id), payload.expected_version,
        {"travel_buffer_minutes": payload.travel_buffer_minutes, "reason": payload.reason, "actor_id": ctx.user_id}))


@router.get("/internal/dispatch/qualifications")
def get_qualifications(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    ctx.require(*STAFF)
    return paged(all_rows(ctx.conn, e.dispatch_qualifications, ctx.tenant_id), page, page_size)


@router.post("/internal/dispatch/qualifications")
def configure_qualification(payload: QualificationInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("pm")

    def run():
        active_member(ctx, payload.user_id, payload.role)
        if payload.service_code not in SERVICE_CODES:
            fail(422, "INVALID_SERVICE", "請選擇已支援的服務。")
        previous = one(ctx.conn, e.dispatch_qualifications, ctx.tenant_id, e.dispatch_qualifications.c.user_id == payload.user_id,
                       e.dispatch_qualifications.c.role == payload.role, e.dispatch_qualifications.c.service_code == payload.service_code)
        return upsert_config(ctx, e.dispatch_qualifications, previous, payload.expected_version, payload.model_dump(exclude={"expected_version"}))
    return idempotent(ctx, request, "dispatch.qualification", payload.model_dump(), run)


@router.get("/internal/dispatch/tools")
def get_tools(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    ctx.require(*STAFF)
    return paged(all_rows(ctx.conn, e.dispatch_tools, ctx.tenant_id), page, page_size)


def dispatch_lock(ctx):
    if ctx.conn.dialect.name == "postgresql":
        ctx.conn.execute(text("SELECT pg_advisory_xact_lock(794138251)"))


@router.post("/internal/dispatch/tools")
def configure_tool(payload: ToolInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("pm")

    def run():
        if len(set(payload.service_codes)) != len(payload.service_codes) or set(payload.service_codes) - SERVICE_CODES:
            fail(422, "INVALID_SERVICE", "工具服務範圍必須為不重複的已支援服務。")
        dispatch_lock(ctx)
        previous = one(ctx.conn, e.dispatch_tools, ctx.tenant_id, e.dispatch_tools.c.name == payload.name)
        if previous:
            reservations = all_rows(ctx.conn, m.resource_slots, None, m.resource_slots.c.tenant_id == ctx.tenant_id,
                m.resource_slots.c.resource.like(f"tool:{ctx.tenant_id}:{previous['id']}:%"), m.resource_slots.c.end_at > m.now())
            if reservations and (not payload.active or payload.capacity < previous["capacity"] or set(previous["service_codes"]) - set(payload.service_codes)):
                fail(409, "TOOL_IN_USE", "工具仍有保留時段，不能縮減容量、服務範圍或停用。")
        return upsert_config(ctx, e.dispatch_tools, previous, payload.expected_version, payload.model_dump(exclude={"expected_version"}))
    return idempotent(ctx, request, "dispatch.tool", payload.model_dump(), run)


def reserve_schedule(ctx, batch, payload):
    """Called inside the existing idempotent scheduling transaction after project authorization."""
    dispatch_lock(ctx)
    policy = dispatch_policy(ctx)
    if policy["status"] != "configured":
        fail(409, "DISPATCH_POLICY_UNCONFIGURED", "請先明示設定交通緩衝政策，再確認排程。")
    for user_id, role in ((payload.engineer_id, "engineer"), (payload.reviewer_id, "reviewer")):
        active_member(ctx, user_id, role)
        qualification = one(ctx.conn, e.dispatch_qualifications, ctx.tenant_id,
            e.dispatch_qualifications.c.user_id == user_id, e.dispatch_qualifications.c.role == role,
            e.dispatch_qualifications.c.service_code == batch["service_code"], e.dispatch_qualifications.c.active.is_(True))
        if not qualification or (qualification["valid_until"] and aware(qualification["valid_until"]) < payload.end_at):
            fail(409, "QUALIFICATION_UNCONFIGURED", "人員或覆核者沒有涵蓋整個時段的有效服務資格。")
    tool = one(ctx.conn, e.dispatch_tools, ctx.tenant_id, e.dispatch_tools.c.name == payload.equipment, e.dispatch_tools.c.active.is_(True))
    if not tool or batch["service_code"] not in tool["service_codes"]:
        fail(409, "TOOL_UNCONFIGURED", "工具容量或服務範圍尚未設定。")
    start = payload.start_at - timedelta(minutes=policy["travel_buffer_minutes"])
    end = payload.end_at + timedelta(minutes=policy["travel_buffer_minutes"])
    people = {f"person:{payload.engineer_id}", f"person:{payload.reviewer_id}"}
    tool_slots = [f"tool:{ctx.tenant_id}:{tool['id']}:{index}" for index in range(tool["capacity"])]
    # Old confirmed equipment reservations remain effective until explicitly rescheduled/cancelled.
    legacy_resource = f"equipment:{payload.equipment}"
    conflicts = all_rows(ctx.conn, m.resource_slots, None,
        m.resource_slots.c.resource.in_([*people, *tool_slots, legacy_resource]), m.resource_slots.c.batch_id != batch["id"],
        m.resource_slots.c.start_at < end, m.resource_slots.c.end_at > start)
    occupied = {row["resource"] for row in conflicts}
    if occupied & (people | {legacy_resource}):
        fail(409, "SCHEDULE_CONFLICT", "人員、覆核者或既有設備時段衝突（含明示設定的交通緩衝）。")
    available = [slot for slot in tool_slots if slot not in occupied]
    if len(available) < payload.equipment_units:
        fail(409, "TOOL_CAPACITY_CONFLICT", "所需工具容量超過此時段可用數量。")
    ctx.conn.execute(delete(m.resource_slots).where(m.resource_slots.c.tenant_id == ctx.tenant_id, m.resource_slots.c.batch_id == batch["id"]))
    for resource in [*sorted(people), *available[:payload.equipment_units]]:
        add(ctx.conn, m.resource_slots, tenant_id=ctx.tenant_id, batch_id=batch["id"], resource=resource, start_at=start, end_at=end)
    return {"policy_version": policy["version"], "travel_buffer_minutes": policy["travel_buffer_minutes"],
            "tool_id": tool["id"], "equipment_units": payload.equipment_units, "status": "verified"}


def seed_synthetic_execution(conn):
    """Explicit local fixture, add missing rows only; never infer production qualifications."""
    if settings().app_env not in {"development", "test"}:
        raise RuntimeError("Synthetic dispatch policy prohibited outside development/test")
    from .seed import fixed, PROFILES
    tenant_id = fixed("tenant-a")
    if not one(conn, m.tenants, None, m.tenants.c.id == tenant_id):
        return {"status": "tenant_not_seeded"}
    set_tenant(conn, tenant_id)
    reason = "明示合成本機測試設定；不代表正式資格、交通或容量政策"
    if not one(conn, e.dispatch_policies, tenant_id):
        add(conn, e.dispatch_policies, tenant_id, travel_buffer_minutes=30, reason=reason, actor_id=fixed("owner-a"))
    for key, (suffix, _, roles) in PROFILES.items():
        if suffix != "a":
            continue
        for role in set(roles) & {"engineer", "reviewer"}:
            for service in sorted(SERVICE_CODES):
                if not one(conn, e.dispatch_qualifications, tenant_id, e.dispatch_qualifications.c.user_id == fixed(key),
                           e.dispatch_qualifications.c.role == role, e.dispatch_qualifications.c.service_code == service):
                    add(conn, e.dispatch_qualifications, tenant_id, user_id=fixed(key), role=role,
                        service_code=service, valid_until=None, active=True, reason=reason)
    for name in ("qa", "kit-a", "test-kit", "uat-kit", "synthetic-uat-kit"):
        if not one(conn, e.dispatch_tools, tenant_id, e.dispatch_tools.c.name == name):
            add(conn, e.dispatch_tools, tenant_id, name=name, capacity=1, service_codes=sorted(SERVICE_CODES), active=True, reason=reason)
    return {"status": "synthetic_missing_rows_added", "existing_values_preserved": True}
