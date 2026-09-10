from datetime import datetime, timedelta
from typing import Annotated, Literal
import json

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field, StringConstraints, field_validator, model_validator
from sqlalchemy import func, select

from . import learning_entitlements as seats, models as m, wallet
from .db import add, all_rows, aware, change, one
from .project_routes import Input
from .security import Context, context, digest, fail, idempotent, owned, paged

router = APIRouter()


class EnrollmentInput(Input):
    course_id: str
    learner_id: str
    cohort: str = Field(default="2026", min_length=1, max_length=80)


class LearnerDeactivateInput(Input):
    reason: str = Field(min_length=1, max_length=1000)


class LearnerDepartmentInput(LearnerDeactivateInput):
    department: str = Field(min_length=1, max_length=120)
    expected_department: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(min_length=0, max_length=120)


class TrainingEntitlementInput(Input):
    course_id: str = Field(min_length=1, max_length=36)
    source: Literal["annual_included", "gift", "manual"]
    quantity: int = Field(ge=1, le=100000, strict=True)
    starts_at: datetime
    expires_at: datetime
    cohort: str | None = Field(default=None, min_length=1, max_length=80)
    contract_id: str | None = Field(default=None, min_length=1, max_length=36)
    source_reference: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("starts_at", "expires_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Timezone is required")
        return value

    @model_validator(mode="after")
    def valid_grant(self):
        if self.expires_at <= self.starts_at or self.expires_at <= m.now():
            raise ValueError("席次效期必須晚於起日且尚未到期")
        if self.source == "annual_included" and not self.contract_id:
            raise ValueError("年度方案內含席次需要有效合約")
        return self


class ProgressInput(Input):
    lesson_id: str
    seconds: int = Field(ge=1, le=3600, strict=True)


class AnswerInput(Input):
    question_id: str
    choice: int = Field(ge=0, le=20, strict=True)


class AttemptInput(Input):
    enrollment_id: str
    answers: list[AnswerInput] = Field(min_length=1, max_length=100)


def course_row(conn, course_id):
    row = one(conn, m.courses, None, m.courses.c.id == course_id)
    if not row or row["status"] not in {"development", "published"}:
        fail(404, "COURSE_NOT_AVAILABLE", "課程尚未開放。")
    return row


def enrollment_row(ctx, enrollment_id, learner=True):
    row = owned(ctx, m.enrollments, enrollment_id)
    if learner and row["learner_id"] != ctx.user_id:
        fail(404, "ENROLLMENT_NOT_FOUND", "找不到您的課程授權。")
    return row


def enrollment_view(ctx, row):
    course = course_row(ctx.conn, row["course_id"])
    lesson_rows = sorted(all_rows(ctx.conn, m.lessons, None, m.lessons.c.course_id == course["id"]), key=lambda item: item["position"])
    progress = all_rows(ctx.conn, m.progress_events, ctx.tenant_id, m.progress_events.c.enrollment_id == row["id"])
    certificate = one(ctx.conn, m.certificates, ctx.tenant_id, m.certificates.c.enrollment_id == row["id"])
    attempts = all_rows(ctx.conn, m.attempts, ctx.tenant_id, m.attempts.c.enrollment_id == row["id"])
    usable = row["status"] in {"active", "completed"} and aware(row["expires_at"]) > m.now()
    return {**row, "course_title": course["title"], "course_version": course["version"],
            "progress_seconds": sum(item["seconds"] for item in progress), "required_seconds": sum(item["min_seconds"] for item in lesson_rows),
            "lessons": [{**{key: value for key, value in lesson.items() if key != "content" or usable},
                         "completed_seconds": next((item["seconds"] for item in progress if item["lesson_id"] == lesson["id"]), 0)} for lesson in lesson_rows],
            "certificate_id": certificate["id"] if certificate else None, "attempts_remaining": max(0, course["max_attempts"]-len(attempts)),
            "expired": aware(row["expires_at"]) <= m.now(), "pass_percent": course["pass_percent"],
            "authorization": seats.authorization_view(ctx.conn, ctx.tenant_id, row)}


def assignment_details(ctx, course_id, learner_id, cohort):
    course = course_row(ctx.conn, course_id)
    if not seats.learner_is_active(ctx.conn, ctx.tenant_id, learner_id):
        fail(404, "LEARNER_NOT_FOUND", "找不到企業內可派課的學員。")
    previous = one(ctx.conn, m.enrollments, ctx.tenant_id, m.enrollments.c.learner_id == learner_id,
                   m.enrollments.c.course_id == course_id, m.enrollments.c.cohort == cohort)
    if previous and previous["status"] == "cancelled":
        fail(409, "COHORT_CANCELLED", "此期授權已取消，重新派課請使用新期別。")
    return course, previous


def assign(ctx, course_id, learner_id, cohort, source="points"):
    course, previous = assignment_details(ctx, course_id, learner_id, cohort)
    if previous:
        return previous
    seats.expire_authorizations(ctx.conn, ctx.tenant_id)
    row_id = m.uid()
    expires_at = m.now()+timedelta(days=14)
    entitlement = seats.eligible_entitlement(ctx.conn, ctx.tenant_id, course_id, cohort)
    if entitlement:
        expires_at = min(expires_at, aware(entitlement["expires_at"]))
        source = entitlement["source"]
        reservation_id = None
    else:
        source = "points"
        reservation = wallet.reserve(ctx.conn, ctx.tenant_id, "training", row_id, course["points"], expires_at)
        reservation_id = reservation["id"]
    row = add(ctx.conn, m.enrollments, ctx.tenant_id, id=row_id, course_id=course_id, learner_id=learner_id,
              cohort=cohort, reservation_id=reservation_id, expires_at=expires_at, source=source)
    if entitlement:
        seats.reserve_seat(ctx.conn, ctx.tenant_id, row, entitlement)
    add(ctx.conn, m.notifications, ctx.tenant_id, user_id=learner_id, title="有新的待修課程", text=course["title"])
    ctx.audit("training.assign", row["id"])
    return row


def training_page(ctx, request, table, page, page_size, *conditions):
    if set(request.query_params)-{"page", "page_size"}:
        fail(422, "INVALID_QUERY", "不接受其他資料範圍參數。")
    query = select(table).where(*conditions)
    if table.name in m.TENANT_TABLES:
        query = query.where(table.c.tenant_id == ctx.tenant_id)
    total = ctx.conn.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = [dict(row) for row in ctx.conn.execute(query.order_by(table.c.created_at.desc(), table.c.id)
             .offset((page-1)*page_size).limit(page_size)).mappings()]
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@router.get("/internal/training/courses")
def training_course_catalog(request: Request, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                            ctx: Context = Depends(context)):
    ctx.require("pm")
    result = training_page(ctx, request, m.courses, page, page_size, m.courses.c.status.in_(["published", "development"]))
    result["items"] = [{key: row[key] for key in ["id", "title", "version", "points", "status"]} for row in result["items"]]
    return result


@router.get("/internal/training/contracts")
def training_contract_catalog(request: Request, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                              ctx: Context = Depends(context)):
    ctx.require("pm")
    result = training_page(ctx, request, m.contracts, page, page_size, m.contracts.c.status == "active")
    result["items"] = [{key: row[key] for key in ["id", "title", "version"]} for row in result["items"]]
    return result


def entitlement_list(ctx, request, page, page_size):
    result = training_page(ctx, request, seats.entitlements, page, page_size)
    result["items"] = [seats.entitlement_view(ctx.conn, ctx.tenant_id, row) for row in result["items"]]
    return result


@router.get("/customer/training/entitlements")
def customer_training_entitlements(request: Request, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                                   ctx: Context = Depends(context)):
    ctx.require("training_manager")
    return entitlement_list(ctx, request, page, page_size)


@router.get("/internal/training/entitlements")
def internal_training_entitlements(request: Request, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                                   ctx: Context = Depends(context)):
    ctx.require("pm")
    return entitlement_list(ctx, request, page, page_size)


@router.post("/internal/training/entitlements")
def create_training_entitlement(payload: TrainingEntitlementInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("pm")
    course_row(ctx.conn, payload.course_id)
    if payload.contract_id and not one(ctx.conn, m.contracts, ctx.tenant_id, m.contracts.c.id == payload.contract_id,
                                       m.contracts.c.status == "active"):
        fail(404, "CONTRACT_NOT_AVAILABLE", "找不到企業內有效的合約。")

    def run():
        row = add(ctx.conn, seats.entitlements, ctx.tenant_id, **payload.model_dump(), granted_by=ctx.user_id)
        ctx.audit("training.entitlement.grant", row["id"], f"source={row['source']}; quantity={row['quantity']}")
        return {"id": row["id"]}
    receipt = idempotent(ctx, request, "training.entitlement.grant", payload.model_dump(), run)
    return seats.entitlement_view(ctx.conn, ctx.tenant_id, owned(ctx, seats.entitlements, receipt["id"]))


@router.get("/customer/training/assignment-preview")
def assignment_preview(request: Request, course_id: str = Query(min_length=1, max_length=36),
                       learner_id: str = Query(min_length=1, max_length=36), cohort: str = Query("2026", min_length=1, max_length=80),
                       ctx: Context = Depends(context)):
    ctx.require("training_manager")
    if set(request.query_params)-{"course_id", "learner_id", "cohort"}:
        fail(422, "INVALID_QUERY", "不接受其他資料範圍參數。")
    course, previous = assignment_details(ctx, course_id, learner_id, cohort)
    if previous:
        result = seats.authorization_view(ctx.conn, ctx.tenant_id, previous)
    else:
        entitlement = seats.eligible_entitlement(ctx.conn, ctx.tenant_id, course_id, cohort, lock=False)
        expires_at = m.now()+timedelta(days=14)
        result = {"source": entitlement["source"] if entitlement else "points", "entitlement_id": entitlement["id"] if entitlement else None,
                  "unit": "enrollment_seat" if entitlement else "point", "quantity": 1 if entitlement else course["points"],
                  "expires_at": min(expires_at, aware(entitlement["expires_at"])) if entitlement else expires_at}
    return {**result, "existing_enrollment_id": previous["id"] if previous else None, "preview": True,
            "notice": "既有授權不新增扣帳；此預覽不預留席次或點數，派課時依當下額度再次核對。"}


@router.get("/customer/training/courses")
def customer_courses(ctx: Context = Depends(context)):
    ctx.require("training_manager")
    return paged(all_rows(ctx.conn, m.courses, None, m.courses.c.status.in_(["published", "development"])))


@router.get("/internal/courses")
def internal_courses(ctx: Context = Depends(context)):
    ctx.require("pm", "reviewer")
    return paged(all_rows(ctx.conn, m.courses))


@router.get("/customer/training/learners")
def learners(ctx: Context = Depends(context)):
    ctx.require("training_manager", "customer_admin")
    members = all_rows(ctx.conn, m.memberships, None, m.memberships.c.tenant_id == ctx.tenant_id,
                       m.memberships.c.role == "learner", m.memberships.c.active.is_(True))
    return paged([{**{key: one(ctx.conn, m.users, None, m.users.c.id == member["user_id"])[key] for key in ["id", "name", "email"]},
                   "department": member["department"] or "", "active": True} for member in members])


def learner_membership(ctx, learner_id):
    row = one(ctx.conn, m.memberships, None, m.memberships.c.tenant_id == ctx.tenant_id,
              m.memberships.c.user_id == learner_id, m.memberships.c.role == "learner")
    if not row:
        fail(404, "LEARNER_NOT_FOUND", "找不到企業內的學員身分。")
    return row


def learner_member_view(ctx, learner_id):
    member = learner_membership(ctx, learner_id)
    user = one(ctx.conn, m.users, None, m.users.c.id == learner_id)
    return {"id": learner_id, "learner_id": learner_id, "name": user["name"], "email": user["email"],
            "department": member["department"] or "", "active": member["active"], "scope": "current_tenant_learner_membership"}


@router.post("/customer/training/learners/{learner_id}/deactivate")
def deactivate_learner(learner_id: str, payload: LearnerDeactivateInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("customer_admin")
    member = learner_membership(ctx, learner_id)

    def run():
        ctx.conn.execute(m.memberships.update().where(m.memberships.c.id == member["id"],
            m.memberships.c.tenant_id == ctx.tenant_id, m.memberships.c.user_id == learner_id,
            m.memberships.c.role == "learner").values(active=False))
        released = seats.release_unstarted_for_learner(ctx.conn, ctx.tenant_id, learner_id, payload.reason)
        add(ctx.conn, m.audit_events, ctx.tenant_id, actor_id=ctx.user_id, action="training.learner.deactivate",
            resource_id=learner_id, trace_id=ctx.trace_id, summary=json.dumps({"reason": payload.reason,
                "department": member["department"] or "", "released_enrollment_ids": released}, ensure_ascii=False))
        return {"id": learner_id, "released_enrollment_ids": released}
    receipt = idempotent(ctx, request, f"training.learner.deactivate:{learner_id}", payload.model_dump(), run)
    return {**learner_member_view(ctx, learner_id), "released_enrollment_ids": receipt["released_enrollment_ids"]}


@router.post("/customer/training/learners/{learner_id}/department")
def change_learner_department(learner_id: str, payload: LearnerDepartmentInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("customer_admin")
    member = learner_membership(ctx, learner_id)

    def run():
        if not member["active"]:
            fail(404, "LEARNER_NOT_FOUND", "學員身分已停用。")
        changed = ctx.conn.execute(m.memberships.update().where(m.memberships.c.id == member["id"],
            m.memberships.c.tenant_id == ctx.tenant_id, m.memberships.c.user_id == learner_id,
            m.memberships.c.role == "learner", m.memberships.c.active.is_(True),
            func.coalesce(m.memberships.c.department, "") == payload.expected_department).values(department=payload.department)).rowcount
        if not changed:
            fail(409, "DEPARTMENT_CHANGED", "學員部門已變更，請重新讀取名單後再操作。")
        add(ctx.conn, m.audit_events, ctx.tenant_id, actor_id=ctx.user_id, action="training.learner.department",
            resource_id=learner_id, trace_id=ctx.trace_id, summary=json.dumps({"reason": payload.reason,
                "previous_department": payload.expected_department, "department": payload.department}, ensure_ascii=False))
        return {"id": learner_id}
    idempotent(ctx, request, f"training.learner.department:{learner_id}", payload.model_dump(), run)
    return learner_member_view(ctx, learner_id)


@router.get("/customer/training/enrollments")
def training_enrollments(ctx: Context = Depends(context)):
    ctx.require("training_manager")
    return paged([enrollment_view(ctx, row) for row in all_rows(ctx.conn, m.enrollments, ctx.tenant_id)])


@router.post("/customer/training/enrollments")
def create_enrollment(payload: EnrollmentInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("training_manager")
    assignment_details(ctx, payload.course_id, payload.learner_id, payload.cohort)
    receipt = idempotent(ctx, request, "training.assign", payload.model_dump(),
                         lambda: {"id": assign(ctx, payload.course_id, payload.learner_id, payload.cohort)["id"]})
    return enrollment_view(ctx, enrollment_row(ctx, receipt["id"], learner=False))


@router.post("/customer/training/enrollments/{enrollment_id}/cancel")
def cancel_enrollment(enrollment_id: str, request: Request, ctx: Context = Depends(context)):
    ctx.require("training_manager")
    row = enrollment_row(ctx, enrollment_id, learner=False)

    def run():
        if row["status"] == "cancelled":
            return row
        if row["status"] != "assigned":
            fail(409, "ENROLLMENT_ALREADY_STARTED", "已啟動課程不能取消釋放席次或點數。")
        seats.release_authorization(ctx.conn, ctx.tenant_id, row, "training cancellation")
        change(ctx.conn, m.enrollments, ctx.tenant_id, enrollment_id, status="cancelled")
        ctx.audit("training.cancel", enrollment_id)
        return enrollment_row(ctx, enrollment_id, learner=False)
    return idempotent(ctx, request, f"training.cancel:{enrollment_id}", {}, run)


@router.get("/learner/enrollments")
def learner_enrollments(ctx: Context = Depends(context)):
    ctx.require("learner")
    return paged([enrollment_view(ctx, row) for row in all_rows(ctx.conn, m.enrollments, ctx.tenant_id, m.enrollments.c.learner_id == ctx.user_id)])


@router.get("/learner/enrollments/{enrollment_id}")
def learner_enrollment(enrollment_id: str, ctx: Context = Depends(context)):
    ctx.require("learner")
    return enrollment_view(ctx, enrollment_row(ctx, enrollment_id))


@router.post("/learner/enrollments/{enrollment_id}/start")
def start_enrollment(enrollment_id: str, request: Request, ctx: Context = Depends(context)):
    ctx.require("learner")
    row = enrollment_row(ctx, enrollment_id)
    if aware(row["expires_at"]) <= m.now():
        fail(410, "COURSE_EXPIRED", "課程授權已到期。")
    if row["status"] not in {"assigned", "active", "completed"}:
        fail(409, "COURSE_NOT_ASSIGNED", "課程授權已取消。")
    course_row(ctx.conn, row["course_id"])

    def run():
        if aware(row["expires_at"]) <= m.now():
            fail(410, "COURSE_EXPIRED", "課程授權已到期。")
        if row["status"] in {"active", "completed"}:
            return {"id": row["id"], "status": row["status"]}
        if row["status"] != "assigned":
            fail(409, "COURSE_NOT_ASSIGNED", "課程授權已取消。")
        course_row(ctx.conn, row["course_id"])
        seats.consume_authorization(ctx.conn, ctx.tenant_id, row)
        change(ctx.conn, m.enrollments, ctx.tenant_id, enrollment_id, status="active", started_at=m.now())
        ctx.audit("training.start", enrollment_id)
        return {"id": enrollment_id, "status": "active"}
    idempotent(ctx, request, f"training.start:{enrollment_id}", {}, run)
    return enrollment_view(ctx, enrollment_row(ctx, enrollment_id))


def active_enrollment(ctx, enrollment_id):
    row = enrollment_row(ctx, enrollment_id)
    if aware(row["expires_at"]) <= m.now():
        fail(410, "COURSE_EXPIRED", "課程授權已到期。")
    if row["status"] not in {"active", "completed"}:
        fail(409, "COURSE_NOT_STARTED", "請先啟動課程。")
    return row


@router.get("/learner/enrollments/{enrollment_id}/lessons")
def enrollment_lessons(enrollment_id: str, ctx: Context = Depends(context)):
    ctx.require("learner")
    row = active_enrollment(ctx, enrollment_id)
    return paged(enrollment_view(ctx, row)["lessons"])


@router.post("/learner/enrollments/{enrollment_id}/progress")
def progress(enrollment_id: str, payload: ProgressInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("learner")
    row = active_enrollment(ctx, enrollment_id)
    lesson = one(ctx.conn, m.lessons, None, m.lessons.c.id == payload.lesson_id, m.lessons.c.course_id == row["course_id"])
    if not lesson:
        fail(404, "LESSON_NOT_FOUND", "此章節不屬於您的課程。")

    def run():
        records = all_rows(ctx.conn, m.progress_events, ctx.tenant_id, m.progress_events.c.enrollment_id == enrollment_id)
        credited = sum(item["seconds"] for item in records)
        elapsed = int((m.now()-aware(row["started_at"])).total_seconds())
        previous = next((item for item in records if item["lesson_id"] == payload.lesson_id), None)
        current = previous["seconds"] if previous else 0
        increment = min(payload.seconds, max(0, lesson["min_seconds"]-current))
        if increment > max(0, elapsed-credited)+1:
            fail(409, "PROGRESS_TOO_FAST", "學習時間尚不足，請閱讀章節後再儲存進度。")
        if previous:
            change(ctx.conn, m.progress_events, ctx.tenant_id, previous["id"], seconds=current+increment, last_at=m.now())
        else:
            add(ctx.conn, m.progress_events, ctx.tenant_id, enrollment_id=enrollment_id, lesson_id=payload.lesson_id,
                seconds=increment, last_at=m.now())
        return enrollment_view(ctx, row)
    return idempotent(ctx, request, f"training.progress:{enrollment_id}", payload.model_dump(), run)


@router.get("/learner/enrollments/{enrollment_id}/questions")
def enrollment_questions(enrollment_id: str, ctx: Context = Depends(context)):
    ctx.require("learner")
    row = active_enrollment(ctx, enrollment_id)
    view = enrollment_view(ctx, row)
    if view["progress_seconds"] < view["required_seconds"]:
        fail(409, "LESSONS_REQUIRED", "請先完成所有章節。")
    return paged([{key: question[key] for key in ["id", "prompt", "choices", "position"]}
                  for question in all_rows(ctx.conn, m.questions, None, m.questions.c.course_id == row["course_id"])])


@router.post("/learner/attempts")
def submit_attempt(payload: AttemptInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("learner")
    row = active_enrollment(ctx, payload.enrollment_id)

    def run():
        course = course_row(ctx.conn, row["course_id"])
        view = enrollment_view(ctx, row)
        if row["status"] == "completed":
            return {"status": "already_completed", "certificate_id": view["certificate_id"]}
        if view["progress_seconds"] < view["required_seconds"] or view["attempts_remaining"] <= 0:
            fail(409, "ASSESSMENT_NOT_READY", "章節未完成或已達測驗次數上限。")
        questions = all_rows(ctx.conn, m.questions, None, m.questions.c.course_id == row["course_id"])
        answers = {answer.question_id: answer.choice for answer in payload.answers}
        if len(answers) != len(payload.answers) or set(answers) != {question["id"] for question in questions}:
            fail(422, "INVALID_ANSWERS", "請完整作答且不要重複提交同一題。")
        if any(answers[q["id"]] >= len(q["choices"]) for q in questions):
            fail(422, "INVALID_CHOICE", "測驗選項無效。")
        score = sum(answers[q["id"]] == q["correct_choice"] for q in questions)*100//len(questions)
        passed = score >= course["pass_percent"]
        attempt = add(ctx.conn, m.attempts, ctx.tenant_id, enrollment_id=row["id"], score=score, passed=passed,
                      question_version=course["version"], answers=[answer.model_dump() for answer in payload.answers])
        certificate = None
        if passed:
            change(ctx.conn, m.enrollments, ctx.tenant_id, row["id"], status="completed", completed_at=m.now())
            certificate_id = m.uid()
            certificate = add(ctx.conn, m.certificates, ctx.tenant_id, id=certificate_id, enrollment_id=row["id"],
                              verification_hash=digest(certificate_id), course_title=course["title"], learner_name=ctx.user["name"], issued_at=m.now())
            add(ctx.conn, m.jobs, id=certificate_id, tenant_id=ctx.tenant_id, kind="certificate_lookup", resource_id=certificate_id, status="active")
        ctx.audit("training.attempt", row["id"], f"score={score}; passed={passed}")
        return {**attempt, "certificate_id": certificate["id"] if certificate else None,
                "explanations": [{"question_id": q["id"], "explanation": q["explanation"]} for q in questions] if passed or view["attempts_remaining"] == 1 else []}
    return idempotent(ctx, request, "training.attempt", payload.model_dump(), run)


@router.get("/learner/certificates/{certificate_id}")
def certificate(certificate_id: str, ctx: Context = Depends(context)):
    ctx.require("learner")
    row = owned(ctx, m.certificates, certificate_id)
    enrollment_row(ctx, row["enrollment_id"])
    return {**row, "verification_code": certificate_id, "notice": "原創示範課程完課紀錄，不代表資安專業認證。"}


@router.get("/learner/enrollments/{enrollment_id}/video-token")
def video_token(enrollment_id: str, ctx: Context = Depends(context)):
    ctx.require("learner")
    active_enrollment(ctx, enrollment_id)
    fail(503, "VIDEO_PROVIDER_DISABLED", "本示範課程提供文字教材；付費影片供應商與教材尚未啟用。")
