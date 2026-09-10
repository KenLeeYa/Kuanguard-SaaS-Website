from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
import copy
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete

from . import entitlements, models as m
from .catalog import SERVICE_CODES
from .config import settings
from .db import add, all_rows, aware, change, one
from .project_execution import dispatch_view, reserve_schedule, router as execution_router, task_views
from .security import Context, context, digest, fail, idempotent, owned, paged

router = APIRouter()
router.include_router(execution_router)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TextInput(Input):
    text: str = Field(min_length=1, max_length=10000)


class ProjectInput(Input):
    name: str = Field(min_length=1, max_length=120)
    company_name: str = Field(min_length=1, max_length=120)
    year: int = Field(ge=2020, le=2100)
    contract_id: str | None = None


class BatchInput(Input):
    service_code: str
    title: str = Field(min_length=1, max_length=120)
    planned_assets: list[str] = Field(default_factory=list, max_length=10000)


class ScheduleInput(Input):
    start_at: datetime
    end_at: datetime
    engineer_id: str
    reviewer_id: str
    equipment: str = Field(min_length=1, max_length=120)
    equipment_units: int = Field(default=1, ge=1, le=100, strict=True)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("start_at", "end_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Timezone is required")
        return value.astimezone(timezone.utc)


class ImportInput(Input):
    batch_id: str
    filename: str = Field(min_length=1, max_length=120)
    content: str = Field(max_length=5_000_000)


class ReviewInput(Input):
    decision: Literal["approved", "returned"]
    note: str = Field(min_length=1, max_length=10000)


class ReportInput(Input):
    batch_id: str


class EntitlementGrantInput(Input):
    project_id: str
    service_code: str
    quantity: int = Field(ge=1, le=100, strict=True)
    reason: str = Field(min_length=10, max_length=1000)


class ChangeOfferInput(Input):
    expected_version: int = Field(ge=1)
    amount_minor: int = Field(ge=0, le=2_000_000_000, strict=True)
    reason: str = Field(min_length=10, max_length=1000)


class ChangeApplyInput(Input):
    expected_version: int = Field(ge=1)
    schedule: ScheduleInput | None = None


class PublicationInput(Input):
    report_job_id: str
    note: str = Field(min_length=1, max_length=10000)


class RetestInput(Input):
    batch_id: str
    finding_ids: list[str] = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=10000)


class AcceptanceInput(Input):
    batch_id: str
    decision: Literal["accepted", "partial", "returned"]
    comment: str = Field(min_length=1, max_length=10000)


class QuoteInput(Input):
    lead_id: str | None = None
    title: str = Field(min_length=1, max_length=120)
    amount_minor: int = Field(ge=0, le=2_000_000_000, strict=True)
    services: list[str] = Field(min_length=1, max_length=7)
    valid_until: datetime


class AcceptQuoteInput(Input):
    version: int
    intent: Literal["accept"]


class ChangeInput(Input):
    batch_id: str
    kind: Literal["reschedule", "scope"]
    reason: str = Field(min_length=1, max_length=10000)
    proposed_assets: list[str] = Field(default_factory=list, max_length=10000)
    proposed_start: datetime | None = None

    @field_validator("proposed_start")
    @classmethod
    def timezone_required(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Timezone is required")
        return value


class TicketInput(Input):
    subject: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=10000)


class RetestProofInput(Input):
    finding_id: str
    method: str = Field(min_length=1, max_length=120)
    scope_confirmed: Literal[True]
    evidence: str = Field(min_length=1, max_length=10000)
    tested_rule_ids: list[str] = Field(default_factory=list, max_length=1000)


class ReviewPolicyInput(Input):
    requires_independent_review: bool
    reason: str = Field(min_length=1, max_length=1000)


def internal(ctx, *roles):
    ctx.require(*(roles or ("pm", "engineer", "reviewer")))


def project_rows(ctx):
    return all_rows(ctx.conn, m.projects, ctx.tenant_id, m.projects.c.id.in_(ctx.project_ids()))


def batch_rows(ctx):
    return all_rows(ctx.conn, m.batches, ctx.tenant_id, m.batches.c.project_id.in_(ctx.project_ids()))


def customer_batch_view(row):
    fields = {"id", "project_id", "package_id", "title", "service_code", "status", "scope_version", "version",
              "start_at", "end_at", "original_start_at", "timezone", "retest_of", "retest_deadline"}
    return {key: value for key, value in row.items() if key in fields}


def publication_rows(ctx):
    allowed = [batch["id"] for batch in batch_rows(ctx)]
    result = []
    for row in all_rows(ctx.conn, m.publications, ctx.tenant_id, m.publications.c.batch_id.in_(allowed)):
        batch = ctx.batch(row["batch_id"])
        snapshot = owned(ctx, m.snapshots, row["snapshot_id"])
        result.append({**row, "service_code": batch["service_code"], "title": batch["title"],
                       "project_id": batch["project_id"], "statistics": snapshot["dataset"].get("statistics", {}),
                       "formats": ["docx", "pdf", "pptx", "xlsx", "csv"], "synthetic": True})
    superseded = {r["supersedes_id"] for r in result if r["supersedes_id"]}
    return [{**row, "superseded": row["id"] in superseded} for row in result]


def published_findings(ctx):
    result = []
    for publication in publication_rows(ctx):
        if publication["superseded"]:
            continue
        snapshot = owned(ctx, m.snapshots, publication["snapshot_id"])
        for finding in snapshot["dataset"].get("findings", []):
            # Internal evidence and parser raw metadata never cross the customer projection.
            result.append({key: finding.get(key) for key in
                           ["id", "source_id", "asset", "title", "severity", "description", "solution", "port", "location", "check_status", "status"]}
                          | {"batch_id": publication["batch_id"], "project_id": publication["project_id"],
                             "service_code": publication["service_code"], "report_version": publication["version"],
                             "publication_id": publication["id"]})
    return result


def detail_project(ctx, project_id, employee=False):
    project = ctx.project(project_id)
    batches = all_rows(ctx.conn, m.batches, ctx.tenant_id, m.batches.c.project_id == project_id)
    if not employee:
        batches = [customer_batch_view(row) for row in batches]
    for batch in batches:
        batch["planned_assets"] = [a["asset"] for a in all_rows(ctx.conn, m.scope_assets, ctx.tenant_id,
                                                            m.scope_assets.c.batch_id == batch["id"],
                                                            m.scope_assets.c.version == batch["scope_version"])]
    comments = all_rows(ctx.conn, m.comments, ctx.tenant_id, m.comments.c.project_id == project_id)
    if not employee:
        comments = [row for row in comments if row["visibility"] == "customer"]
    return {**project, "work_packages": all_rows(ctx.conn, m.work_packages, ctx.tenant_id, m.work_packages.c.project_id == project_id),
            "batches": batches, "milestones": task_views(ctx, project_id, employee),
            "comments": comments, "findings": [row for row in published_findings(ctx) if row["project_id"] == project_id],
            "reports": [row for row in publication_rows(ctx) if row["project_id"] == project_id],
            "entitlements": [entitlements.balance(ctx.conn, ctx.tenant_id, row) for row in all_rows(ctx.conn, m.entitlements, ctx.tenant_id, m.entitlements.c.project_id == project_id)],
            "acceptances": all_rows(ctx.conn, m.acceptances, ctx.tenant_id, m.acceptances.c.project_id == project_id),
            "changes": all_rows(ctx.conn, m.changes, ctx.tenant_id, m.changes.c.project_id == project_id)}


@router.get("/customer/projects")
def customer_projects(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    ctx.require("customer_contact")
    return paged(project_rows(ctx), page, page_size)


@router.get("/customer/projects/{project_id}")
def customer_project(project_id: str, ctx: Context = Depends(context)):
    ctx.require("customer_contact")
    return detail_project(ctx, project_id)


@router.get("/internal/projects")
def internal_projects(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    internal(ctx)
    return paged(project_rows(ctx), page, page_size)


@router.get("/internal/projects/{project_id}")
def internal_project(project_id: str, ctx: Context = Depends(context)):
    internal(ctx)
    return detail_project(ctx, project_id, employee=True)


@router.post("/internal/projects")
def create_project(payload: ProjectInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "pm")

    def run():
        if payload.contract_id:
            contract = owned(ctx, m.contracts, payload.contract_id)
            quote = one(ctx.conn, m.quotes, ctx.tenant_id, m.quotes.c.id == contract["quote_id"])
            if contract["status"] != "active" or not quote or quote["status"] != "accepted" or quote["amount_minor"] != contract["amount_minor"]:
                fail(409, "CONTRACT_NOT_ACTIVE", "請選擇已確認報價且仍有效的同企業合約。")
        row = add(ctx.conn, m.projects, ctx.tenant_id, **payload.model_dump())
        add(ctx.conn, m.grants, ctx.tenant_id, user_id=ctx.user_id, resource_id=row["id"], reason="project owner")
        for code in sorted(SERVICE_CODES):
            add(ctx.conn, m.work_packages, ctx.tenant_id, project_id=row["id"], service_code=code)
        ctx.audit("project.create", row["id"])
        return row
    return idempotent(ctx, request, "project.create", payload.model_dump(), run)


@router.post("/internal/projects/{project_id}/batches")
def create_batch(project_id: str, payload: BatchInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "pm")
    ctx.project(project_id)
    if payload.service_code not in SERVICE_CODES:
        fail(422, "INVALID_SERVICE", "未識別的服務。")

    def run():
        package = one(ctx.conn, m.work_packages, ctx.tenant_id, m.work_packages.c.project_id == project_id,
                      m.work_packages.c.service_code == payload.service_code)
        row = add(ctx.conn, m.batches, ctx.tenant_id, project_id=project_id, package_id=package["id"],
                  service_code=payload.service_code, title=payload.title, retest_deadline=m.now()+timedelta(days=90))
        for asset in sorted(set(payload.planned_assets)):
            if len(asset) > 500:
                fail(422, "INVALID_ASSET", "資產名稱過長。")
            add(ctx.conn, m.scope_assets, ctx.tenant_id, batch_id=row["id"], asset=asset, version=1)
        entitlements.reserve(ctx.conn, ctx.tenant_id, row)
        ctx.audit("batch.create", row["id"])
        return row
    return idempotent(ctx, request, f"batch.create:{project_id}", payload.model_dump(), run)


@router.get("/internal/dispatch")
def dispatch(ctx: Context = Depends(context)):
    return dispatch_view(ctx)


@router.post("/internal/batches/{batch_id}/schedule")
def schedule_batch(batch_id: str, payload: ScheduleInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "pm")
    batch = ctx.batch(batch_id)
    if batch["status"] in {"delivered", "approved", "cancelled"}:
        fail(409, "BATCH_STATE", "批次狀態不允許改期。")
    if payload.start_at >= payload.end_at or payload.start_at <= m.now():
        fail(422, "INVALID_WINDOW", "排程需在未來且結束晚於開始。")
    if payload.engineer_id == payload.reviewer_id and ctx.project(batch["project_id"])["requires_independent_review"]:
        fail(409, "SEPARATION_REQUIRED", "工程師與覆核者必須不同。")
    def run():
        checks = reserve_schedule(ctx, batch, payload)
        for user_id in {payload.engineer_id, payload.reviewer_id}:
            grant = one(ctx.conn, m.grants, ctx.tenant_id, m.grants.c.user_id == user_id,
                        m.grants.c.resource_id == batch["project_id"], m.grants.c.scope == "project")
            if not grant:
                add(ctx.conn, m.grants, ctx.tenant_id, user_id=user_id, resource_id=batch["project_id"], reason="confirmed assignment")
            elif grant["expires_at"] and aware(grant["expires_at"]) <= m.now():
                change(ctx.conn, m.grants, ctx.tenant_id, grant["id"], expires_at=None, reason="confirmed assignment renewed project access")
        add(ctx.conn, m.schedule_history, ctx.tenant_id, batch_id=batch_id, old_start=batch["start_at"], new_start=payload.start_at,
            new_end=payload.end_at, reason=payload.reason, actor_id=ctx.user_id)
        change(ctx.conn, m.batches, ctx.tenant_id, batch_id, start_at=payload.start_at, end_at=payload.end_at,
               original_start_at=batch["original_start_at"] or payload.start_at, engineer_id=payload.engineer_id,
               reviewer_id=payload.reviewer_id, equipment=payload.equipment, status="confirmed", version=batch["version"]+1)
        ctx.audit("batch.schedule", batch_id, f"policy_version={checks['policy_version']}; tool_units={checks['equipment_units']}; {payload.reason}")
        return {**owned(ctx, m.batches, batch_id), "scheduling_checks": checks}
    return idempotent(ctx, request, f"batch.schedule:{batch_id}", payload.model_dump(), run)


@router.get("/customer/calendar")
def calendar(ctx: Context = Depends(context)):
    ctx.require("customer_contact")
    return paged([{key: row[key] for key in ["id", "title", "project_id", "service_code", "status", "start_at", "end_at", "timezone"]}
                  for row in batch_rows(ctx) if row["start_at"] and row["status"] not in {"preparing", "cancelled"}])


@router.post("/internal/imports/preview")
def preview_import(payload: ImportInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "engineer")
    batch = ctx.batch(payload.batch_id)
    if batch["engineer_id"] != ctx.user_id:
        fail(403, "ASSIGNMENT_REQUIRED", "只有本批次指派工程師可匯入。")
    if batch["status"] in {"approved", "delivered", "cancelled"}:
        fail(409, "BATCH_LOCKED", "核定批次已鎖定，請建立新批次或更正版本。")
    if batch["service_code"] not in {"VA", "WVA", "SHC", "PT", "SOURCE"}:
        fail(422, "IMPORT_SERVICE", "此服務使用專屬活動或學習流程。")
    if Path(payload.filename).name != payload.filename or any(character in payload.filename for character in "\\/:"):
        fail(422, "INVALID_FILENAME", "檔名不能包含路徑。")
    data = payload.content.encode("utf-8")
    if len(data) > settings().max_import_bytes:
        fail(413, "IMPORT_TOO_LARGE", "本機匯入上限 5 MB。")

    def run():
        from .parsers import parse_assessment
        source_hash = digest(data)
        existing = one(ctx.conn, m.imports, ctx.tenant_id, m.imports.c.batch_id == batch["id"], m.imports.c.source_hash == source_hash)
        if existing:
            return {**existing, **existing["parsed"], "parsed": None}
        assets = [a["asset"] for a in all_rows(ctx.conn, m.scope_assets, ctx.tenant_id, m.scope_assets.c.batch_id == batch["id"],
                                            m.scope_assets.c.version == batch["scope_version"])]
        parsed = parse_assessment(payload.filename, data, batch["service_code"], assets)
        import_id = m.uid()
        key = f"{ctx.tenant_id}/quarantine/{import_id}/{source_hash}"
        destination = settings().local_data_dir / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        row = add(ctx.conn, m.imports, ctx.tenant_id, id=import_id, batch_id=batch["id"], filename=payload.filename,
                  source_hash=source_hash, object_key=key, size=len(data), parser_version=parsed.get("parser_version", "unknown"),
                  parsed=parsed, status="invalid" if parsed.get("errors") else "preview", actor_id=ctx.user_id)
        ctx.audit("import.preview", import_id, f"sha256={source_hash}; bytes={len(data)}")
        return {**row, **parsed, "parsed": None}
    return idempotent(ctx, request, "import.preview", payload.model_dump(), run)


@router.get("/internal/imports")
def list_imports(ctx: Context = Depends(context)):
    internal(ctx, "engineer", "reviewer")
    ids = [batch["id"] for batch in batch_rows(ctx)]
    return paged([{key: value for key, value in row.items() if key not in {"parsed", "object_key"}}
                  for row in all_rows(ctx.conn, m.imports, ctx.tenant_id, m.imports.c.batch_id.in_(ids))])


@router.post("/internal/imports/{import_id}/commit")
def commit_import(import_id: str, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "engineer")
    row = owned(ctx, m.imports, import_id)
    batch = ctx.batch(row["batch_id"])
    if batch["engineer_id"] != ctx.user_id:
        fail(403, "ASSIGNMENT_REQUIRED", "只有本批次指派工程師可提交。")

    def run():
        if row["status"] == "committed":
            return {"id": row["id"], "status": "committed"}
        if row["status"] != "preview" or row["parsed"].get("errors") or batch["status"] in {"approved", "delivered", "cancelled"}:
            fail(409, "IMPORT_NOT_READY", "匯入有錯誤或批次已鎖定。")
        path = settings().local_data_dir / row["object_key"]
        if not path.exists() or digest(path.read_bytes()) != row["source_hash"]:
            fail(409, "SOURCE_HASH_MISMATCH", "原始檔完整性驗證失敗。")
        for finding in row["parsed"]["findings"]:
            fingerprint = finding_fingerprint(finding)
            existing = one(ctx.conn, m.findings, ctx.tenant_id, m.findings.c.batch_id == batch["id"], m.findings.c.fingerprint == fingerprint)
            values = {key: finding.get(key) for key in ["source_id", "asset", "title", "severity", "description", "solution", "location", "check_status"]}
            values.update(evidence=json.dumps(finding.get("evidence", ""), ensure_ascii=False) if not isinstance(finding.get("evidence", ""), str) else finding.get("evidence", ""),
                          port=str(finding["port"]) if finding.get("port") is not None else None, details=finding)
            if existing:
                # CSV is authoritative for VA when both formats exist; keep the source difference in audit.
                old_import = owned(ctx, m.imports, existing["source_import_id"])
                if batch["service_code"] == "VA" and row["filename"].lower().endswith(".csv"):
                    change(ctx.conn, m.findings, ctx.tenant_id, existing["id"], **values, source_import_id=import_id)
                ctx.audit("import.duplicate_source", existing["id"], f"previous_import={old_import['id']}; current_import={import_id}")
            else:
                add(ctx.conn, m.findings, ctx.tenant_id, batch_id=batch["id"], source_import_id=import_id, fingerprint=fingerprint, **values)
        for item in row["parsed"].get("coverage", []):
            previous = one(ctx.conn, m.coverage, ctx.tenant_id, m.coverage.c.batch_id == batch["id"], m.coverage.c.asset == item["asset"])
            if previous:
                # Proven failure wins; auxiliary CSV without scan evidence cannot erase completion.
                priority = {"not_tested": 0, "insufficient": 1, "completed": 2, "failed": 3}
                if priority[item["status"]] >= priority[previous["status"]]:
                    change(ctx.conn, m.coverage, ctx.tenant_id, previous["id"], status=item["status"], source_import_id=import_id)
            else:
                add(ctx.conn, m.coverage, ctx.tenant_id, batch_id=batch["id"], asset=item["asset"], status=item["status"], source_import_id=import_id)
        change(ctx.conn, m.imports, ctx.tenant_id, import_id, status="committed")
        change(ctx.conn, m.batches, ctx.tenant_id, batch["id"], status="awaiting_review", reviewed_by=None, reviewed_at=None)
        ctx.audit("import.commit", import_id)
        return {"id": import_id, "status": "committed", "batch_id": batch["id"]}
    return idempotent(ctx, request, f"import.commit:{import_id}", {}, run)


def finding_fingerprint(finding):
    keys = (["method", "source_id", "source_fingerprint"] if finding.get("source_fingerprint") else
            ["source_id", "asset", "port", "location_hash", "location", "rule_id", "http_method", "parameter", "protocol", "line", "column"])
    return digest(json.dumps([finding.get(key) for key in keys], ensure_ascii=False, sort_keys=True))


def check_review_policy(ctx, batch):
    if ctx.project(batch["project_id"])["requires_independent_review"] and batch["reviewed_by"] == batch["engineer_id"]:
        fail(403, "SEPARATION_REQUIRED", "目前合約要求獨立覆核，請由符合政策的覆核者重新核定。")


@router.post("/internal/batches/{batch_id}/review")
def review_batch(batch_id: str, payload: ReviewInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "reviewer")
    batch = ctx.batch(batch_id)
    if ctx.user_id != batch["reviewer_id"]:
        fail(403, "REVIEWER_ASSIGNMENT_REQUIRED", "需由本批次指派覆核者核定。")
    if ctx.user_id == batch["engineer_id"] and ctx.project(batch["project_id"])["requires_independent_review"]:
        fail(403, "SEPARATION_REQUIRED", "本專案合約要求獨立覆核者。")

    def run():
        if batch["status"] != "awaiting_review":
            fail(409, "REVIEW_STATE", "批次尚未進入待覆核。")
        committed = all_rows(ctx.conn, m.imports, ctx.tenant_id, m.imports.c.batch_id == batch_id, m.imports.c.status == "committed")
        if not committed:
            fail(409, "NO_DATA", "需先完成有效匯入。")
        change(ctx.conn, m.batches, ctx.tenant_id, batch_id, status="approved" if payload.decision == "approved" else "preparing",
               reviewed_by=ctx.user_id if payload.decision == "approved" else None, reviewed_at=m.now(), review_note=payload.note)
        ctx.audit("batch.review", batch_id, payload.note)
        return owned(ctx, m.batches, batch_id)
    return idempotent(ctx, request, f"batch.review:{batch_id}", payload.model_dump(), run)


@router.post("/internal/report-jobs")
def create_report_job(payload: ReportInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "reviewer")
    batch = ctx.batch(payload.batch_id)
    check_review_policy(ctx, batch)

    def run():
        from .reports import build_snapshot
        if batch["status"] not in {"approved", "delivered"} or batch["reviewed_by"] != ctx.user_id:
            fail(409, "REVIEW_REQUIRED", "需由核定覆核者建立報告。")
        sources = all_rows(ctx.conn, m.imports, ctx.tenant_id, m.imports.c.batch_id == batch["id"], m.imports.c.status == "committed")
        if not sources:
            fail(409, "NO_DATA", "需先完成有效匯入。")
        committed_at = {entry["resource_id"]: entry["created_at"] for entry in all_rows(ctx.conn, m.audit_events, ctx.tenant_id,
            m.audit_events.c.action == "import.commit", m.audit_events.c.resource_id.in_([source["id"] for source in sources]))}
        sources.sort(key=lambda row: committed_at.get(row["id"], row["created_at"]), reverse=True)
        findings = all_rows(ctx.conn, m.findings, ctx.tenant_id, m.findings.c.batch_id == batch["id"])
        finding_ids = {row["fingerprint"]: row["id"] for row in findings}
        previous = all_rows(ctx.conn, m.snapshots, ctx.tenant_id, m.snapshots.c.batch_id == batch["id"])
        version = max([p["version"] for p in previous], default=0)+1
        source_metadata = [source["parsed"].get("metadata", {}) for source in sources]
        csv_authority = batch["service_code"] == "VA" and any(metadata.get("format") == "nessus-csv" for metadata in source_metadata)
        planned_assets = [asset["asset"] for asset in all_rows(ctx.conn, m.scope_assets, ctx.tenant_id,
            m.scope_assets.c.batch_id == batch["id"], m.scope_assets.c.version == batch["scope_version"])]
        parsed_sources = []
        for source in sources:
            parsed = copy.deepcopy(source["parsed"])
            for finding in parsed["findings"]:
                finding["id"] = finding_ids[finding_fingerprint(finding)]
            parsed["metadata"]["planned_assets"] = planned_assets
            for field in ["disabled_rules", "excluded_paths"]:
                parsed["metadata"][field] = sorted({item for metadata in source_metadata for item in metadata.get(field, [])})
            parsed["metadata"]["source_metadata"] = source_metadata
            parsed["metadata"]["source_selection_policy"] = "latest-committed-csv-whole-source-v1" if csv_authority else "merge-latest-committed-occurrence-v1"
            parsed["metadata"]["source_import_order"] = [source_row["id"] for source_row in sources]
            parsed["warnings"] = [warning for source_row in sources for warning in source_row["parsed"].get("warnings", [])]
            parsed_sources.append(parsed)
        report_context = {"batch_id": batch["id"], "service_code": batch["service_code"],
                  "scope_version": batch["scope_version"], "reviewer_id": ctx.user_id, "reviewed_at": aware(batch["reviewed_at"]).isoformat(),
                  "report_version": version, "synthetic": True, "project_name": ctx.project(batch["project_id"])["name"],
                  "title": batch["title"], "tenant_name": ctx.tenant["name"],
                  "additional_sources": parsed_sources[1:], "source_precedence": "csv" if csv_authority else "merge"}
        if batch["retest_of"]:
            baseline_publications = all_rows(ctx.conn, m.publications, ctx.tenant_id, m.publications.c.batch_id == batch["retest_of"])
            if not baseline_publications:
                fail(409, "BASELINE_NOT_PUBLISHED", "複測需關聯已發布的初測版本。")
            latest = max(baseline_publications, key=lambda row: row["version"])
            baseline = owned(ctx, m.snapshots, latest["snapshot_id"])["dataset"]
            report_context["baseline_snapshot"] = baseline
            proofs = all_rows(ctx.conn, m.retest_checks, ctx.tenant_id, m.retest_checks.c.retest_batch_id == batch["id"])
            occurrence_ids = {finding["id"]: finding["occurrence_id"] for finding in baseline["findings"]}
            report_context["verified_absent"] = [{**proof, "occurrence_id": occurrence_ids.get(proof["finding_id"])} for proof in proofs]
            report_context["tested_rule_ids"] = sorted({rule for proof in proofs for rule in proof["tested_rule_ids"]})
        dataset = build_snapshot(parsed_sources[0], report_context)
        snapshot = add(ctx.conn, m.snapshots, ctx.tenant_id, batch_id=batch["id"], version=version,
                       sha256=digest(json.dumps(dataset, ensure_ascii=False, sort_keys=True)), dataset=dataset, reviewer_id=ctx.user_id)
        job = add(ctx.conn, m.report_jobs, ctx.tenant_id, batch_id=batch["id"], snapshot_id=snapshot["id"])
        add(ctx.conn, m.jobs, tenant_id=ctx.tenant_id, kind="report", resource_id=job["id"])
        ctx.audit("report.request", job["id"])
        return job
    return idempotent(ctx, request, "report.create", payload.model_dump(), run)


@router.get("/internal/report-jobs")
def list_report_jobs(ctx: Context = Depends(context)):
    internal(ctx, "engineer", "reviewer")
    ids = [row["id"] for row in batch_rows(ctx)]
    return paged(all_rows(ctx.conn, m.report_jobs, ctx.tenant_id, m.report_jobs.c.batch_id.in_(ids)))


@router.get("/internal/report-jobs/{job_id}")
def report_job_detail(job_id: str, ctx: Context = Depends(context)):
    internal(ctx, "engineer", "reviewer")
    job = owned(ctx, m.report_jobs, job_id)
    ctx.batch(job["batch_id"])
    return {**job, "snapshot": owned(ctx, m.snapshots, job["snapshot_id"])["dataset"]}


@router.get("/internal/report-jobs/{job_id}/download/{format}")
def report_job_download(job_id: str, format: str, ctx: Context = Depends(context)):
    internal(ctx, "engineer", "reviewer")
    job = owned(ctx, m.report_jobs, job_id)
    ctx.batch(job["batch_id"])
    artifact = next((item for item in (job["manifest"] or {}).get("artifacts", []) if item["format"] == format), None)
    if not artifact or job["status"] != "completed":
        fail(404, "ARTIFACT_NOT_READY", "此報告檔案尚未產製完成。")
    path = settings().local_data_dir / job["output_key"] / artifact["filename"]
    if not path.is_file() or digest(path.read_bytes()) != artifact["sha256"]:
        fail(409, "ARTIFACT_HASH_MISMATCH", "檔案完整性驗證失敗。")
    ctx.audit("report.internal_preview", job_id, f"format={format}")
    return FileResponse(path, filename=f"KUANGUARD-review-{job_id[:8]}.{format}", headers={"Cache-Control": "private, no-store"})


@router.post("/internal/publications")
def publish(payload: PublicationInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "reviewer")
    job = owned(ctx, m.report_jobs, payload.report_job_id)
    batch = ctx.batch(job["batch_id"])
    check_review_policy(ctx, batch)

    def run():
        if batch["reviewed_by"] != ctx.user_id or job["status"] != "completed" or batch["status"] not in {"approved", "delivered"}:
            fail(409, "PUBLICATION_NOT_READY", "只有核定覆核者可發布完成產製的報告。")
        manifest = job["manifest"] or {}
        formats = {artifact["format"] for artifact in manifest.get("artifacts", [])}
        if not {"docx", "pdf", "pptx", "xlsx", "csv"}.issubset(formats):
            fail(409, "BUNDLE_INCOMPLETE", "報告格式不完整，無法發布。")
        directory = settings().local_data_dir / job["output_key"]
        for artifact in manifest["artifacts"]:
            path = directory / artifact["filename"]
            if not path.is_file() or digest(path.read_bytes()) != artifact["sha256"]:
                fail(409, "ARTIFACT_HASH_MISMATCH", "報告檔案完整性驗證失敗。")
        existing = one(ctx.conn, m.publications, ctx.tenant_id, m.publications.c.report_job_id == job["id"])
        if existing:
            return existing
        prior = sorted(all_rows(ctx.conn, m.publications, ctx.tenant_id, m.publications.c.batch_id == batch["id"]), key=lambda row: row["version"])
        snapshot = owned(ctx, m.snapshots, job["snapshot_id"])
        if (snapshot["dataset"]["reviewed_at"] != aware(batch["reviewed_at"]).isoformat()
                or str(snapshot["dataset"]["scope_version"]) != str(batch["scope_version"])):
            fail(409, "STALE_APPROVAL", "報告快照與目前核定或範圍版本不同。")
        if prior and snapshot["version"] <= prior[-1]["version"]:
            fail(409, "STALE_REPORT_VERSION", "舊版報告不能覆蓋新版。")
        row = add(ctx.conn, m.publications, ctx.tenant_id, batch_id=batch["id"], report_job_id=job["id"], snapshot_id=snapshot["id"],
                  version=snapshot["version"], published_by=ctx.user_id, note=payload.note, supersedes_id=prior[-1]["id"] if prior else None)
        entitlements.finish(ctx.conn, ctx.tenant_id, batch, "consume", "核定報告首次交付，結算一批次額度")
        change(ctx.conn, m.batches, ctx.tenant_id, batch["id"], status="delivered")
        ctx.audit("report.publish", row["id"], payload.note)
        return {**row, "synthetic": True, "production_ready": False}
    return idempotent(ctx, request, "report.publish", payload.model_dump(), run)


@router.get("/customer/reports")
def customer_reports(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    ctx.require("customer_contact")
    return paged(publication_rows(ctx), page, page_size)


@router.get("/internal/reports")
def internal_reports(ctx: Context = Depends(context)):
    internal(ctx, "engineer", "reviewer")
    return paged(publication_rows(ctx))


@router.get("/customer/reports/{publication_id}/download/{format}")
def download_report(publication_id: str, format: str, ctx: Context = Depends(context)):
    ctx.require("customer_contact")
    publication = owned(ctx, m.publications, publication_id)
    ctx.batch(publication["batch_id"])
    job = owned(ctx, m.report_jobs, publication["report_job_id"])
    artifact = next((item for item in (job["manifest"] or {}).get("artifacts", []) if item["format"] == format), None)
    if not artifact:
        fail(404, "ARTIFACT_NOT_FOUND", "找不到報告格式。")
    path = settings().local_data_dir / job["output_key"] / artifact["filename"]
    if not path.is_file() or digest(path.read_bytes()) != artifact["sha256"]:
        fail(409, "ARTIFACT_INVALID", "報告完整性驗證失敗。")
    ctx.audit("report.download", publication_id, f"format={format}")
    return FileResponse(path, filename=f"KUANGUARD-{publication_id[:8]}-v{publication['version']}.{format}", headers={"Cache-Control": "private, no-store"})


@router.get("/customer/findings")
def customer_findings(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), severity: str | None = None):
    ctx.require("customer_contact")
    rows = published_findings(ctx)
    if severity:
        if severity not in {"Critical", "High", "Medium", "Low", "Informational", "Unknown"}:
            fail(422, "INVALID_FILTER", "無效風險篩選。")
        rows = [row for row in rows if row["severity"] == severity]
    return paged(rows, page, page_size)


@router.get("/customer/findings/{finding_id}")
def customer_finding(finding_id: str, ctx: Context = Depends(context)):
    ctx.require("customer_contact")
    row = next((row for row in published_findings(ctx) if row["id"] == finding_id), None)
    if not row:
        fail(404, "FINDING_NOT_PUBLISHED", "找不到可存取的已發布結果。")
    return {**row, "comments": all_rows(ctx.conn, m.comments, ctx.tenant_id, m.comments.c.finding_id == finding_id,
                                       m.comments.c.visibility == "customer")}


@router.get("/internal/findings")
def internal_findings(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), batch_id: str | None = None, service_code: str | None = None):
    internal(ctx, "engineer", "reviewer")
    allowed = [row["id"] for row in batch_rows(ctx) if (not batch_id or row["id"] == batch_id) and (not service_code or row["service_code"] == service_code)]
    return paged(all_rows(ctx.conn, m.findings, ctx.tenant_id, m.findings.c.batch_id.in_(allowed)), page, page_size)


@router.post("/customer/findings/{finding_id}/replies")
def reply(finding_id: str, payload: TextInput, request: Request, ctx: Context = Depends(context)):
    row = customer_finding(finding_id, ctx)

    def run():
        result = add(ctx.conn, m.comments, ctx.tenant_id, project_id=row["project_id"], finding_id=finding_id, text=payload.text, actor_id=ctx.user_id)
        ctx.audit("finding.reply", finding_id)
        # Customer reply is a claim awaiting verification; never rewrites the published snapshot or marks fixed.
        return {**result, "remediation_status": "awaiting_verification"}
    return idempotent(ctx, request, f"finding.reply:{finding_id}", payload.model_dump(), run)


@router.post("/customer/retest-requests")
def request_retest(payload: RetestInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("customer_contact")
    batch = ctx.batch(payload.batch_id)
    allowed = {row["id"] for row in published_findings(ctx) if row["batch_id"] == payload.batch_id}
    if not set(payload.finding_ids).issubset(allowed):
        fail(404, "FINDING_NOT_PUBLISHED", "複測僅能選擇本批次已發布的發現。")
    if not batch["retest_deadline"] or aware(batch["retest_deadline"]) < m.now():
        fail(409, "RETEST_EXPIRED", "複測期限已到，請申請新範圍報價。")

    def run():
        row = add(ctx.conn, m.retest_requests, ctx.tenant_id, **payload.model_dump(), actor_id=ctx.user_id)
        ctx.audit("retest.request", row["id"])
        return row
    return idempotent(ctx, request, "retest.request", payload.model_dump(), run)


@router.post("/customer/projects/{project_id}/comments")
def project_comment(project_id: str, payload: TextInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("customer_contact")
    ctx.project(project_id)
    return idempotent(ctx, request, f"comment:{project_id}", payload.model_dump(),
                      lambda: add(ctx.conn, m.comments, ctx.tenant_id, project_id=project_id, text=payload.text, actor_id=ctx.user_id))


@router.post("/customer/projects/{project_id}/acceptance")
def acceptance(project_id: str, payload: AcceptanceInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("customer_contact")
    ctx.project(project_id)
    batch = ctx.batch(payload.batch_id)
    if batch["project_id"] != project_id or batch["status"] != "delivered":
        fail(409, "ACCEPTANCE_NOT_READY", "僅能驗收本專案已交付的批次。")

    def run():
        row = add(ctx.conn, m.acceptances, ctx.tenant_id, project_id=project_id, actor_id=ctx.user_id, **payload.model_dump())
        ctx.audit("batch.acceptance", payload.batch_id, payload.decision)
        return row
    return idempotent(ctx, request, f"acceptance:{project_id}", payload.model_dump(), run)


@router.get("/internal/leads")
def leads(ctx: Context = Depends(context)):
    internal(ctx, "pm")
    return paged(all_rows(ctx.conn, m.leads))


@router.get("/internal/quotes")
def internal_quotes(ctx: Context = Depends(context)):
    internal(ctx, "pm", "finance")
    return paged(all_rows(ctx.conn, m.quotes, ctx.tenant_id))


def save_quote(ctx, payload, family_id=None, version=1):
    if not set(payload.services).issubset(SERVICE_CODES) or aware(payload.valid_until) <= m.now():
        fail(422, "INVALID_QUOTE", "報價服務或效期無效。")
    return add(ctx.conn, m.quotes, ctx.tenant_id, family_id=family_id or m.uid(), version=version,
               status="offered", **payload.model_dump())


@router.post("/internal/quotes")
def create_quote(payload: QuoteInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "pm")
    return idempotent(ctx, request, "quote.create", payload.model_dump(), lambda: save_quote(ctx, payload))


@router.post("/internal/quotes/{quote_id}/revise")
def revise_quote(quote_id: str, payload: QuoteInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "pm")
    previous = owned(ctx, m.quotes, quote_id)

    def run():
        family = all_rows(ctx.conn, m.quotes, ctx.tenant_id, m.quotes.c.family_id == previous["family_id"])
        version = max(row["version"] for row in family)+1
        result = save_quote(ctx, payload, previous["family_id"], version)
        ctx.audit("quote.revise", result["id"], f"prior={quote_id}")
        return result
    return idempotent(ctx, request, f"quote.revise:{quote_id}", payload.model_dump(), run)


@router.get("/customer/quotes")
def customer_quotes(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    ctx.require("customer_contact")
    return paged(all_rows(ctx.conn, m.quotes, ctx.tenant_id, m.quotes.c.status.in_(["offered", "accepted"])), page, page_size)


@router.post("/customer/quotes/{quote_id}/accept")
def accept_quote(quote_id: str, payload: AcceptQuoteInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("customer_contact")
    quote = owned(ctx, m.quotes, quote_id)

    def run():
        family = all_rows(ctx.conn, m.quotes, ctx.tenant_id, m.quotes.c.family_id == quote["family_id"])
        if quote["version"] != payload.version or quote["version"] != max(row["version"] for row in family):
            fail(409, "STALE_QUOTE", "報價已有新版，請重新確認。")
        if aware(quote["valid_until"]) <= m.now():
            fail(409, "QUOTE_EXPIRED", "報價已過期。")
        existing = one(ctx.conn, m.contracts, ctx.tenant_id, m.contracts.c.quote_id == quote_id)
        if existing:
            return existing
        if quote["status"] != "offered":
            fail(409, "QUOTE_STATE", "此報價不能確認。")
        change(ctx.conn, m.quotes, ctx.tenant_id, quote_id, status="accepted", accepted_by=ctx.user_id, accepted_at=m.now())
        contract = add(ctx.conn, m.contracts, ctx.tenant_id, quote_id=quote_id, title=quote["title"], version=quote["version"],
                       amount_minor=quote["amount_minor"], services=quote["services"], accepted_by=ctx.user_id)
        ctx.audit("quote.accept", quote_id, f"intent=accept; version={payload.version}; sandbox confirmation")
        return contract
    return idempotent(ctx, request, f"quote.accept:{quote_id}", payload.model_dump(), run)


@router.get("/customer/contracts")
def customer_contracts(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    ctx.require("customer_contact")
    return paged(all_rows(ctx.conn, m.contracts, ctx.tenant_id), page, page_size)


@router.get("/customer/entitlements")
def customer_entitlements(ctx: Context = Depends(context)):
    ctx.require("customer_contact")
    return paged([entitlements.balance(ctx.conn, ctx.tenant_id, row) for row in
                  all_rows(ctx.conn, m.entitlements, ctx.tenant_id, m.entitlements.c.project_id.in_(ctx.project_ids()))])


@router.get("/customer/projects/{project_id}/changes")
def list_changes(project_id: str, ctx: Context = Depends(context)):
    ctx.require("customer_contact")
    ctx.project(project_id)
    return paged(all_rows(ctx.conn, m.changes, ctx.tenant_id, m.changes.c.project_id == project_id))


@router.post("/customer/projects/{project_id}/changes")
def request_change(project_id: str, payload: ChangeInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("customer_contact")
    ctx.project(project_id)
    if ctx.batch(payload.batch_id)["project_id"] != project_id:
        fail(404, "BATCH_NOT_FOUND", "批次不屬於此專案。")
    return idempotent(ctx, request, f"change.request:{project_id}", payload.model_dump(),
                      lambda: add(ctx.conn, m.changes, ctx.tenant_id, project_id=project_id, requested_by=ctx.user_id, **payload.model_dump()))


@router.get("/customer/tickets")
def customer_tickets(ctx: Context = Depends(context)):
    ctx.require("customer_contact", "customer_admin", "campaign_manager", "training_manager", "billing_manager", "learner")
    return paged(all_rows(ctx.conn, m.tickets, ctx.tenant_id, m.tickets.c.actor_id == ctx.user_id))


@router.post("/customer/tickets")
def create_ticket(payload: TicketInput, request: Request, ctx: Context = Depends(context)):
    return idempotent(ctx, request, "ticket.create", payload.model_dump(),
                      lambda: add(ctx.conn, m.tickets, ctx.tenant_id, actor_id=ctx.user_id, **payload.model_dump()))


@router.get("/customer/organization")
def organization(ctx: Context = Depends(context)):
    ctx.require("customer_admin")
    members = all_rows(ctx.conn, m.memberships, None, m.memberships.c.tenant_id == ctx.tenant_id)
    rows = {}
    for member in members:
        # Company administration does not expose employee staffing or unrelated internal roles.
        if member["role"] in {"engineer", "reviewer", "finance", "pm", "platform_admin", "portfolio_owner"}:
            continue
        user = one(ctx.conn, m.users, None, m.users.c.id == member["user_id"])
        rows.setdefault(user["id"], {"id": user["id"], "name": user["name"], "email": user["email"],
                                     "department": member["department"], "active": member["active"], "roles": []})["roles"].append(member["role"])
    return paged(list(rows.values()))


@router.get("/internal/audit")
def audit(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    internal(ctx, "pm", "reviewer", "finance", "platform_admin")
    rows = sorted(all_rows(ctx.conn, m.audit_events, ctx.tenant_id, m.audit_events.c.actor_id == ctx.user_id), key=lambda row: row["created_at"], reverse=True)
    return paged(rows, page, page_size)


@router.get("/internal/retest-requests")
def internal_retests(ctx: Context = Depends(context)):
    internal(ctx, "pm", "engineer", "reviewer")
    return paged(all_rows(ctx.conn, m.retest_requests, ctx.tenant_id, m.retest_requests.c.batch_id.in_([row["id"] for row in batch_rows(ctx)])))


@router.post("/internal/retest-requests/{request_id}/approve")
def approve_retest(request_id: str, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "pm")
    retest = owned(ctx, m.retest_requests, request_id)
    original = ctx.batch(retest["batch_id"])

    def run():
        if retest["status"] != "requested":
            fail(409, "RETEST_REQUEST_STATE", "此申請已處理。")
        if not original["retest_deadline"] or aware(original["retest_deadline"]) <= m.now():
            fail(409, "RETEST_EXPIRED", "原複測資格已到期。")
        batch = add(ctx.conn, m.batches, ctx.tenant_id, project_id=original["project_id"], package_id=original["package_id"],
                    service_code=original["service_code"], title=original["title"][:95]+"・複測", retest_of=original["id"],
                    engineer_id=original["engineer_id"], reviewer_id=original["reviewer_id"], retest_deadline=original["retest_deadline"])
        for asset in all_rows(ctx.conn, m.scope_assets, ctx.tenant_id, m.scope_assets.c.batch_id == original["id"], m.scope_assets.c.version == original["scope_version"]):
            add(ctx.conn, m.scope_assets, ctx.tenant_id, batch_id=batch["id"], asset=asset["asset"], version=1)
        entitlements.reserve(ctx.conn, ctx.tenant_id, batch)
        change(ctx.conn, m.retest_requests, ctx.tenant_id, request_id, status="approved")
        ctx.audit("retest.approve", batch["id"], f"source_request={request_id}; baseline_batch={original['id']}")
        return batch
    return idempotent(ctx, request, f"retest.approve:{request_id}", {}, run)


@router.post("/internal/batches/{batch_id}/retest-verifications")
def verify_retest(batch_id: str, payload: RetestProofInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "reviewer")
    batch = ctx.batch(batch_id)
    if not batch["retest_of"] or batch["reviewer_id"] != ctx.user_id or batch["status"] not in {"awaiting_review", "approved"}:
        fail(409, "RETEST_REVIEW_STATE", "需由複測指派覆核者在待覆核階段填寫驗證證據。")
    finding = owned(ctx, m.findings, payload.finding_id)
    if finding["batch_id"] != batch["retest_of"] or payload.method != finding["details"].get("method"):
        fail(409, "RETEST_SCOPE_MISMATCH", "驗證方法或初測發現不符合複測來源。")
    current_coverage = one(ctx.conn, m.coverage, ctx.tenant_id, m.coverage.c.batch_id == batch_id, m.coverage.c.asset == finding["asset"])
    if not current_coverage or current_coverage["status"] != "completed":
        fail(409, "RETEST_NOT_COVERED", "原資產尚未完成本次複測，不能標示已驗證修復。")

    def run():
        if one(ctx.conn, m.retest_checks, ctx.tenant_id, m.retest_checks.c.retest_batch_id == batch_id, m.retest_checks.c.finding_id == payload.finding_id):
            fail(409, "RETEST_PROOF_EXISTS", "驗證證據已存在，需新複測版本更正。")
        row = add(ctx.conn, m.retest_checks, ctx.tenant_id, retest_batch_id=batch_id, reviewer_id=ctx.user_id, **payload.model_dump())
        ctx.audit("retest.verify", row["id"], f"method={payload.method}; original_finding={finding['id']}")
        return row
    return idempotent(ctx, request, f"retest.verify:{batch_id}", payload.model_dump(), run)


@router.post("/internal/projects/{project_id}/review-policy")
def review_policy(project_id: str, payload: ReviewPolicyInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("portfolio_owner")
    project = ctx.project(project_id)

    def run():
        if project["requires_independent_review"] and not payload.requires_independent_review:
            fail(409, "CONTRACT_POLICY_CHANGE_REQUIRED", "已設定的合約獨立覆核要求不可透過一般設定停用。")
        change(ctx.conn, m.projects, ctx.tenant_id, project_id, requires_independent_review=payload.requires_independent_review, review_policy_reason=payload.reason)
        ctx.audit("project.review_policy", project_id, payload.reason)
        return ctx.project(project_id)
    return idempotent(ctx, request, f"project.policy:{project_id}", payload.model_dump(), run)


@router.post("/internal/entitlements/grants")
def grant_entitlement(payload: EntitlementGrantInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "pm")
    ctx.project(payload.project_id)
    if payload.service_code not in SERVICE_CODES:
        fail(422, "INVALID_SERVICE", "服務代碼無效。")

    def run():
        row = add(ctx.conn, m.entitlements, ctx.tenant_id, project_id=payload.project_id, service_code=payload.service_code, quantity=payload.quantity)
        add(ctx.conn, m.entitlement_ledger, ctx.tenant_id, entitlement_id=row["id"], kind="grant", quantity=payload.quantity,
            business_key=f"grant:{row['id']}", reason=payload.reason)
        ctx.audit("entitlement.grant", row["id"], payload.reason)
        return entitlements.balance(ctx.conn, ctx.tenant_id, row)
    return idempotent(ctx, request, "entitlement.grant", payload.model_dump(), run)


@router.post("/internal/batches/{batch_id}/cancel")
def cancel_batch(batch_id: str, payload: TextInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "pm")
    batch = ctx.batch(batch_id)

    def run():
        if one(ctx.conn, m.publications, ctx.tenant_id, m.publications.c.batch_id == batch_id):
            fail(409, "DELIVERED_BATCH", "已交付批次需保留交付紀錄，不能取消已耗用額度。")
        entitlements.finish(ctx.conn, ctx.tenant_id, batch, "release", payload.text)
        change(ctx.conn, m.batches, ctx.tenant_id, batch_id, status="cancelled", reviewed_by=None, reviewed_at=None)
        ctx.conn.execute(delete(m.resource_slots).where(m.resource_slots.c.tenant_id == ctx.tenant_id, m.resource_slots.c.batch_id == batch_id))
        ctx.audit("batch.cancel", batch_id, payload.text)
        return owned(ctx, m.batches, batch_id)
    return idempotent(ctx, request, f"batch.cancel:{batch_id}", payload.model_dump(), run)


@router.post("/internal/batches/{batch_id}/reopen")
def reopen_batch(batch_id: str, payload: TextInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "pm")
    batch = ctx.batch(batch_id)

    def run():
        if batch["status"] not in {"approved", "delivered"}:
            fail(409, "REOPEN_STATE", "只有已核定或已交付批次可提出更正。")
        change(ctx.conn, m.batches, ctx.tenant_id, batch_id, status="preparing", reviewed_by=None, reviewed_at=None, version=batch["version"]+1)
        ctx.audit("batch.correction_open", batch_id, payload.text)
        return owned(ctx, m.batches, batch_id)
    return idempotent(ctx, request, f"batch.reopen:{batch_id}", payload.model_dump(), run)


@router.post("/internal/batches/{batch_id}/submit-review")
def submit_existing_for_review(batch_id: str, payload: TextInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "engineer")
    batch = ctx.batch(batch_id)
    if batch["engineer_id"] != ctx.user_id:
        fail(403, "ASSIGNMENT_REQUIRED", "需由指派工程師送審。")

    def run():
        if batch["status"] not in {"preparing", "confirmed"} or not one(ctx.conn, m.imports, ctx.tenant_id, m.imports.c.batch_id == batch_id, m.imports.c.status == "committed"):
            fail(409, "REVIEW_STATE", "需有已提交來源及待處理批次才可送審。")
        change(ctx.conn, m.batches, ctx.tenant_id, batch_id, status="awaiting_review", reviewed_by=None, reviewed_at=None)
        ctx.audit("batch.resubmit_review", batch_id, payload.text)
        return owned(ctx, m.batches, batch_id)
    return idempotent(ctx, request, f"batch.resubmit_review:{batch_id}", payload.model_dump(), run)


@router.get("/internal/changes")
def internal_changes(ctx: Context = Depends(context), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    internal(ctx, "pm")
    return paged(all_rows(ctx.conn, m.changes, ctx.tenant_id, m.changes.c.project_id.in_(ctx.project_ids())), page, page_size)


@router.post("/internal/changes/{change_id}/offer")
def offer_change(change_id: str, payload: ChangeOfferInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "pm")
    row = owned(ctx, m.changes, change_id)
    ctx.project(row["project_id"])

    def run():
        if row["status"] not in {"requested", "offered"} or row["version"] != payload.expected_version:
            fail(409, "STALE_CHANGE", "變更單已有新版或已確認。")
        change(ctx.conn, m.changes, ctx.tenant_id, change_id, old_amount_minor=row["new_amount_minor"],
               new_amount_minor=payload.amount_minor, version=row["version"]+1, status="offered")
        ctx.audit("change.offer", change_id, f"v{row['version']} amount={row['new_amount_minor']} -> {payload.amount_minor}; {payload.reason}")
        return owned(ctx, m.changes, change_id)
    return idempotent(ctx, request, f"change.offer:{change_id}", payload.model_dump(), run)


@router.post("/customer/changes/{change_id}/confirm")
def confirm_change(change_id: str, payload: AcceptQuoteInput, request: Request, ctx: Context = Depends(context)):
    ctx.require("customer_contact")
    row = owned(ctx, m.changes, change_id)
    ctx.project(row["project_id"])

    def run():
        if row["status"] != "offered" or row["version"] != payload.version:
            fail(409, "STALE_CHANGE", "請確認最新的範圍與費用版本。")
        change(ctx.conn, m.changes, ctx.tenant_id, change_id, status="confirmed", confirmed_by=ctx.user_id)
        ctx.audit("change.confirm", change_id, f"version={payload.version}; intent=accept; amount_minor={row['new_amount_minor']}")
        return owned(ctx, m.changes, change_id)
    return idempotent(ctx, request, f"change.confirm:{change_id}", payload.model_dump(), run)


@router.post("/internal/changes/{change_id}/apply")
def apply_change(change_id: str, payload: ChangeApplyInput, request: Request, ctx: Context = Depends(context)):
    internal(ctx, "pm")
    row = owned(ctx, m.changes, change_id)
    batch = ctx.batch(row["batch_id"])

    def run():
        if row["status"] != "confirmed" or row["version"] != payload.expected_version:
            fail(409, "CHANGE_CONFIRMATION_REQUIRED", "需客戶確認此版本的範圍與費用。")
        if batch["status"] not in {"preparing", "confirmed"} or one(ctx.conn, m.imports, ctx.tenant_id, m.imports.c.batch_id == batch["id"]):
            fail(409, "SCOPE_ALREADY_EXECUTED", "已執行或匯入的批次需建立新的追加批次，保留原範圍。")
        if row["kind"] == "scope":
            if not row["proposed_assets"] or any(len(asset) > 500 or not asset.strip() for asset in row["proposed_assets"]):
                fail(422, "INVALID_SCOPE", "追加範圍需列出有效資產。")
            previous = {asset["asset"] for asset in all_rows(ctx.conn, m.scope_assets, ctx.tenant_id, m.scope_assets.c.batch_id == batch["id"], m.scope_assets.c.version == batch["scope_version"])}
            version = batch["scope_version"]+1
            for asset in sorted(previous | set(row["proposed_assets"])):
                add(ctx.conn, m.scope_assets, ctx.tenant_id, batch_id=batch["id"], asset=asset, version=version)
            change(ctx.conn, m.batches, ctx.tenant_id, batch["id"], scope_version=version, version=batch["version"]+1)
        else:
            if not payload.schedule or not row["proposed_start"] or payload.schedule.start_at != aware(row["proposed_start"]):
                fail(422, "SCHEDULE_CONFIRMATION_MISMATCH", "套用排程需符合客戶確認的開始時間。")
            schedule_batch(batch["id"], payload.schedule, request, ctx)
        change(ctx.conn, m.changes, ctx.tenant_id, change_id, status="applied")
        ctx.audit("change.apply", change_id, f"confirmed_by={row['confirmed_by']}; version={row['version']}")
        return owned(ctx, m.changes, change_id)
    return idempotent(ctx, request, f"change.apply:{change_id}", payload.model_dump(), run)
