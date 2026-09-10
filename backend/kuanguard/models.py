"""Relational schema. Tenant references use composite keys; immutable records are append-only."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint,
    Integer, MetaData, String, Table, Text, UniqueConstraint,
)

metadata = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


def col(name, kind=String(120), *args, **kwargs):
    return Column(name, kind, *args, **kwargs)


TENANT_TABLES = []


def table(name, *columns, tenant=True, constraints=()):
    common = [col("id", String(36), primary_key=True, default=uid),
              col("created_at", DateTime(timezone=True), nullable=False, default=now)]
    if tenant:
        common.append(Column("tenant_id", String(36), ForeignKey("tenants.id"), nullable=False, index=True))
        constraints = (*constraints, UniqueConstraint("tenant_id", "id"))
        TENANT_TABLES.append(name)
    return Table(name, metadata, *common, *columns, *constraints)


def ref(column, target):
    return ForeignKeyConstraint(["tenant_id", column], [f"{target}.tenant_id", f"{target}.id"])


tenants = table("tenants", col("name", nullable=False), col("verified", Boolean, default=False),
                col("status", default="active"), tenant=False)
users = table("users", col("name", nullable=False), col("email", String(254), nullable=False, unique=True),
              col("oidc_subject", String(400), unique=True), col("active", Boolean, default=True), tenant=False)
# Authentication records must be accessible before selecting a tenant; never exposed as arbitrary lists.
memberships = table("memberships", col("tenant_id", String(36), ForeignKey("tenants.id"), nullable=False),
                    col("user_id", String(36), ForeignKey("users.id"), nullable=False),
                    col("role", nullable=False), col("department", default=""),
                    col("active", Boolean, default=True), tenant=False,
                    constraints=(UniqueConstraint("tenant_id", "user_id", "role"),))
sessions = table("sessions", col("token_hash", String(64), nullable=False, unique=True),
                 col("tenant_id", String(36), ForeignKey("tenants.id"), nullable=False),
                 col("user_id", String(36), ForeignKey("users.id"), nullable=False),
                 col("csrf_token", String(64), nullable=False), col("expires_at", DateTime(timezone=True)),
                 col("revoked", Boolean, default=False), tenant=False)
oidc_states = table("oidc_states", col("state_hash", String(64), unique=True), col("nonce"),
                   col("verifier", String(128)), col("expires_at", DateTime(timezone=True)), tenant=False)
grants = table("grants", col("user_id", String(36), ForeignKey("users.id")), col("resource_id", String(36)),
               col("scope", default="project"), col("expires_at", DateTime(timezone=True)),
               col("reason", Text, default=""), constraints=(UniqueConstraint("tenant_id", "user_id", "resource_id", "scope"),))
invitations = table("invitations", col("email", String(254)), col("role"), col("department"),
                    col("token_hash", String(64)), col("expires_at", DateTime(timezone=True)), col("status", default="pending"))
service_catalog = table("service_catalog", col("code", unique=True), col("slug", unique=True), col("name"),
                        col("mode"), col("summary", Text), col("deliverables", JSON), col("version", Integer, default=1), tenant=False)
leads = table("leads", col("company"), col("contact_name"), col("email", String(254)), col("services", JSON),
              col("scope", Text), col("desired_date", String(30)), col("status", default="new"), tenant=False)
quotes = table("quotes", col("family_id", String(36)), col("version", Integer), col("title"),
               col("amount_minor", Integer), col("currency", default="TWD"), col("services", JSON),
               col("valid_until", DateTime(timezone=True)), col("status", default="draft"),
               col("accepted_by", String(36)), col("accepted_at", DateTime(timezone=True)),
               col("lead_id", String(36), ForeignKey("leads.id")),
               constraints=(UniqueConstraint("tenant_id", "family_id", "version"), CheckConstraint("amount_minor >= 0", name="quote_amount")))
contracts = table("contracts", col("quote_id", String(36)), col("title"), col("status", default="active"),
                  col("version", Integer, default=1), col("amount_minor", Integer), col("services", JSON),
                  col("accepted_by", String(36)), constraints=(ref("quote_id", "quotes"), UniqueConstraint("tenant_id", "quote_id")))
projects = table("projects", col("name"), col("year", Integer), col("status", default="active"),
                 col("contract_id", String(36)), col("company_name"), col("timezone", default="Asia/Taipei"),
                 col("requires_independent_review", Boolean, nullable=False, default=False, server_default="false"),
                 col("review_policy_reason", Text, default="single-owner standard policy"),
                 constraints=(ref("contract_id", "contracts"),))
work_packages = table("work_packages", col("project_id", String(36), nullable=False), col("service_code"),
                      col("status", default="planned"), col("allowance", Integer, default=1),
                      constraints=(ref("project_id", "projects"), UniqueConstraint("tenant_id", "project_id", "service_code")))
batches = table("batches", col("project_id", String(36), nullable=False), col("package_id", String(36)),
                col("service_code"), col("title"), col("status", default="preparing"),
                col("scope_version", Integer, default=1), col("version", Integer, default=1),
                col("engineer_id", String(36)), col("reviewer_id", String(36)), col("reviewed_by", String(36)),
                col("reviewed_at", DateTime(timezone=True)), col("start_at", DateTime(timezone=True)),
                col("end_at", DateTime(timezone=True)), col("original_start_at", DateTime(timezone=True)),
                col("equipment"), col("timezone", default="Asia/Taipei"), col("retest_of", String(36)),
                col("retest_deadline", DateTime(timezone=True)), col("review_note", Text),
                constraints=(ref("project_id", "projects"), ref("package_id", "work_packages"), ref("retest_of", "batches")))
scope_assets = table("scope_assets", col("batch_id", String(36)), col("asset", String(500)),
                     col("version", Integer), constraints=(ref("batch_id", "batches"), UniqueConstraint("tenant_id", "batch_id", "asset", "version")))
schedule_history = table("schedule_history", col("batch_id", String(36)), col("old_start", DateTime(timezone=True)),
                         col("new_start", DateTime(timezone=True)), col("new_end", DateTime(timezone=True)),
                         col("reason", Text), col("actor_id", String(36)), constraints=(ref("batch_id", "batches"),))
# Minimal global resource reservation index, no project/customer evidence, needed for cross-tenant conflict prevention.
resource_slots = table("resource_slots", col("tenant_id", String(36)), col("batch_id", String(36)), col("resource"),
                       col("start_at", DateTime(timezone=True)), col("end_at", DateTime(timezone=True)), tenant=False)
tasks = table("tasks", col("project_id", String(36)), col("batch_id", String(36)), col("title"),
              col("status", default="open"), col("due_at", DateTime(timezone=True)), col("assigned_to", String(36)),
              col("visibility", default="customer"), constraints=(ref("project_id", "projects"), ref("batch_id", "batches")))
changes = table("changes", col("project_id", String(36)), col("batch_id", String(36)), col("kind"),
                col("reason", Text), col("proposed_assets", JSON), col("proposed_start", DateTime(timezone=True)),
                col("old_amount_minor", Integer, default=0), col("new_amount_minor", Integer, default=0),
                col("status", default="requested"), col("version", Integer, default=1),
                col("requested_by", String(36)), col("confirmed_by", String(36)),
                constraints=(ref("project_id", "projects"), ref("batch_id", "batches")))
comments = table("comments", col("project_id", String(36)), col("finding_id", String(36)), col("text", Text),
                 col("visibility", default="customer"), col("actor_id", String(36)),
                 constraints=(ref("project_id", "projects"),))
acceptances = table("acceptances", col("project_id", String(36)), col("batch_id", String(36)), col("decision"),
                    col("comment", Text), col("actor_id", String(36)),
                    constraints=(ref("project_id", "projects"), ref("batch_id", "batches")))
time_entries = table("time_entries", col("project_id", String(36)), col("category"), col("minutes", Integer),
                     col("cost_minor", Integer), col("actor_id", String(36)), col("note", Text),
                     constraints=(ref("project_id", "projects"), CheckConstraint("minutes >= 0 AND cost_minor >= 0", name="nonnegative_time_cost")))
imports = table("imports", col("batch_id", String(36)), col("filename"), col("source_hash", String(64)),
                col("object_key", String(500)), col("size", Integer), col("parser_version"), col("parsed", JSON),
                col("status", default="preview"), col("actor_id", String(36)),
                constraints=(ref("batch_id", "batches"), UniqueConstraint("tenant_id", "batch_id", "source_hash")))
coverage = table("coverage", col("batch_id", String(36)), col("asset", String(500)), col("status"),
                 col("source_import_id", String(36)), constraints=(ref("batch_id", "batches"), ref("source_import_id", "imports"),
                 UniqueConstraint("tenant_id", "batch_id", "asset")))
findings = table("findings", col("batch_id", String(36)), col("source_import_id", String(36)), col("source_id"),
                 col("fingerprint", String(64)), col("asset", String(500)), col("title", Text), col("severity"),
                 col("description", Text), col("solution", Text), col("port", String(30)), col("location", Text),
                 col("evidence", Text), col("check_status"), col("status", default="open"), col("details", JSON),
                 constraints=(ref("batch_id", "batches"), ref("source_import_id", "imports"), UniqueConstraint("tenant_id", "batch_id", "fingerprint")))
dispositions = table("dispositions", col("finding_id", String(36)), col("decision"), col("reason", Text),
                     col("reviewer_id", String(36)), col("expires_at", DateTime(timezone=True)), constraints=(ref("finding_id", "findings"),))
retest_requests = table("retest_requests", col("batch_id", String(36)), col("finding_ids", JSON), col("reason", Text),
                        col("status", default="requested"), col("actor_id", String(36)), constraints=(ref("batch_id", "batches"),))
retest_checks = table("retest_checks", col("finding_id", String(36)), col("retest_batch_id", String(36)), col("method"),
                      col("scope_confirmed", Boolean), col("evidence", Text), col("reviewer_id", String(36)), col("tested_rule_ids", JSON),
                      constraints=(ref("finding_id", "findings"), ref("retest_batch_id", "batches"), UniqueConstraint("tenant_id", "finding_id", "retest_batch_id")))
snapshots = table("snapshots", col("batch_id", String(36)), col("version", Integer), col("sha256", String(64)),
                  col("dataset", JSON), col("reviewer_id", String(36)),
                  constraints=(ref("batch_id", "batches"), UniqueConstraint("tenant_id", "batch_id", "version")))
report_jobs = table("report_jobs", col("batch_id", String(36)), col("snapshot_id", String(36)), col("status", default="queued"),
                    col("manifest", JSON), col("output_key", String(500)), col("error", Text),
                    constraints=(ref("batch_id", "batches"), ref("snapshot_id", "snapshots"), UniqueConstraint("tenant_id", "snapshot_id")))
publications = table("publications", col("batch_id", String(36)), col("report_job_id", String(36)),
                     col("snapshot_id", String(36)), col("version", Integer), col("published_by", String(36)),
                     col("note", Text), col("supersedes_id", String(36)),
                     constraints=(ref("batch_id", "batches"), ref("report_job_id", "report_jobs"), ref("snapshot_id", "snapshots"),
                     ref("supersedes_id", "publications"), UniqueConstraint("tenant_id", "report_job_id")))
wallets = table("wallets", col("frozen", Boolean, default=False), col("policy_version", default="sandbox-2026-09-v1"),
                constraints=(UniqueConstraint("tenant_id"),))
orders = table("orders", col("points", Integer), col("amount_minor", Integer), col("currency", default="TWD"),
               col("status", default="pending"), col("rate_version", default="sandbox-2026-09-v1"),
               col("provider", default="sandbox"), col("terms", Text), col("actor_id", String(36)),
               constraints=(CheckConstraint("points > 0 AND amount_minor > 0", name="positive_order"),))
payments = table("payments", col("order_id", String(36)), col("provider_ref", unique=True), col("amount_minor", Integer),
                 col("currency"), col("status"), constraints=(ref("order_id", "orders"), UniqueConstraint("tenant_id", "order_id")))
payment_routes = table("payment_routes", col("tenant_id", String(36), ForeignKey("tenants.id")),
                       col("order_id", String(36), unique=True), col("merchant", default="kuanguard-sandbox"), tenant=False)
point_lots = table("point_lots", col("order_id", String(36)), col("source"), col("purpose", default="all"),
                   col("quantity", Integer), col("expires_at", DateTime(timezone=True)), col("paid_amount_minor", Integer, default=0),
                   constraints=(ref("order_id", "orders"), CheckConstraint("quantity > 0", name="positive_lot")))
reservations = table("reservations", col("purpose"), col("business_id", String(120)), col("quantity", Integer),
                     col("status", default="reserved"), col("expires_at", DateTime(timezone=True)),
                     col("policy_version", default="sandbox-2026-09-v1"),
                     constraints=(UniqueConstraint("tenant_id", "purpose", "business_id"), CheckConstraint("quantity > 0", name="positive_reservation")))
reservation_lots = table("reservation_lots", col("reservation_id", String(36)), col("lot_id", String(36)), col("quantity", Integer),
                         constraints=(ref("reservation_id", "reservations"), ref("lot_id", "point_lots"),
                         UniqueConstraint("tenant_id", "reservation_id", "lot_id")))
wallet_transactions = table("wallet_transactions", col("lot_id", String(36)), col("reservation_id", String(36)),
                           col("kind"), col("business_key", String(240)), col("available_delta", Integer, default=0),
                           col("reserved_delta", Integer, default=0), col("consumed_delta", Integer, default=0),
                           col("expired_delta", Integer, default=0), col("refunded_delta", Integer, default=0),
                           col("reason", Text), constraints=(ref("lot_id", "point_lots"), ref("reservation_id", "reservations"),
                           UniqueConstraint("tenant_id", "business_key", "lot_id")))
refunds = table("refunds", col("order_id", String(36)), col("amount_minor", Integer), col("points", Integer),
                col("status"), col("reason", Text), col("actor_id", String(36)), constraints=(ref("order_id", "orders"),))
invoices = table("invoices", col("order_id", String(36)), col("status", default="adapter_disabled"), col("attempts", Integer, default=0),
                 constraints=(ref("order_id", "orders"), UniqueConstraint("tenant_id", "order_id")))
entitlements = table("entitlements", col("project_id", String(36)), col("service_code"), col("unit", default="batch"),
                     col("quantity", Integer), constraints=(ref("project_id", "projects"),))
entitlement_ledger = table("entitlement_ledger", col("entitlement_id", String(36)), col("batch_id", String(36)),
                           col("kind"), col("quantity", Integer), col("business_key", unique=True), col("reason", Text),
                           constraints=(ref("entitlement_id", "entitlements"), ref("batch_id", "batches")))
recipient_groups = table("recipient_groups", col("name"), col("owner_id", String(36)), col("version", Integer, default=1))
recipients = table("recipients", col("group_id", String(36)), col("email", String(254)), col("name"), col("department"),
                   col("learner_id", String(36)), constraints=(ref("group_id", "recipient_groups"), UniqueConstraint("tenant_id", "group_id", "email")))
campaigns = table("campaigns", col("name"), col("group_id", String(36)), col("owner_id", String(36)),
                  col("scheduled_at", DateTime(timezone=True)), col("status", default="draft"),
                  col("remediation_course_id", String(36)), col("timezone", default="Asia/Taipei"),
                  col("rate_version", default="sandbox-2026-09-v1"), col("provider", default="sandbox"),
                  col("template_revision", default="awareness-original-v1"), constraints=(ref("group_id", "recipient_groups"),))
message_plans = table("message_plans", col("campaign_id", String(36)), col("recipient_id", String(36)),
                      col("reservation_id", String(36)), col("status", default="planned"), col("provider_ref"),
                      col("accepted_at", DateTime(timezone=True)), col("tracking_hash", String(64)),
                      constraints=(ref("campaign_id", "campaigns"), ref("recipient_id", "recipients"), ref("reservation_id", "reservations"),
                      UniqueConstraint("tenant_id", "campaign_id", "recipient_id")))
raw_events = table("raw_events", col("campaign_id", String(36)), col("message_id", String(36)), col("event_type"),
                   col("provider_event_id", String(240)), col("occurred_at", DateTime(timezone=True)),
                   col("classification", default="unverified_candidate"), col("classification_version", default="v1"),
                   constraints=(ref("campaign_id", "campaigns"), ref("message_id", "message_plans"), UniqueConstraint("tenant_id", "provider_event_id")))
courses = table("courses", col("slug", unique=True), col("title"), col("version", Integer), col("description", Text),
                col("preview", Text), col("points", Integer), col("duration_minutes", Integer), col("pass_percent", Integer, default=80),
                col("max_attempts", Integer, default=3), col("status", default="development"), col("rights", Text),
                col("language", default="zh-TW"), tenant=False)
lessons = table("lessons", col("course_id", String(36), ForeignKey("courses.id")), col("title"), col("content", Text),
                col("position", Integer), col("min_seconds", Integer), col("video_id"), tenant=False)
questions = table("questions", col("course_id", String(36), ForeignKey("courses.id")), col("prompt", Text),
                  col("choices", JSON), col("correct_choice", Integer), col("explanation", Text), col("position", Integer), tenant=False)
enrollments = table("enrollments", col("course_id", String(36), ForeignKey("courses.id")), col("learner_id", String(36), ForeignKey("users.id")),
                    col("cohort"), col("status", default="assigned"), col("reservation_id", String(36)),
                    col("expires_at", DateTime(timezone=True)), col("started_at", DateTime(timezone=True)),
                    col("completed_at", DateTime(timezone=True)), col("source", default="points"),
                    constraints=(ref("reservation_id", "reservations"), UniqueConstraint("tenant_id", "course_id", "learner_id", "cohort")))
progress_events = table("progress_events", col("enrollment_id", String(36)), col("lesson_id", String(36), ForeignKey("lessons.id")),
                        col("seconds", Integer), col("last_at", DateTime(timezone=True)),
                        constraints=(ref("enrollment_id", "enrollments"), UniqueConstraint("tenant_id", "enrollment_id", "lesson_id")))
attempts = table("attempts", col("enrollment_id", String(36)), col("score", Integer), col("passed", Boolean),
                 col("question_version", Integer), col("answers", JSON), constraints=(ref("enrollment_id", "enrollments"),))
certificates = table("certificates", col("enrollment_id", String(36)), col("verification_hash", String(64)),
                     col("course_title"), col("learner_name"), col("issued_at", DateTime(timezone=True)),
                     constraints=(ref("enrollment_id", "enrollments"), UniqueConstraint("tenant_id", "enrollment_id")))
tickets = table("tickets", col("subject"), col("text", Text), col("status", default="open"), col("actor_id", String(36)))
notifications = table("notifications", col("user_id", String(36)), col("title"), col("text", Text), col("read_at", DateTime(timezone=True)))
questionnaires = table("questionnaires", col("title"), col("supplier"), col("due_at", DateTime(timezone=True)), col("status", default="open"))
questionnaire_answers = table("questionnaire_answers", col("questionnaire_id", String(36)), col("question", Text),
                              col("answer", Text), col("evidence_reference", Text), col("review_status", default="unreviewed"),
                              constraints=(ref("questionnaire_id", "questionnaires"),))
retention_policies = table("retention_policies", col("data_class"), col("days", Integer), col("version", Integer), col("approved", Boolean, default=False))
deletion_requests = table("deletion_requests", col("data_class"), col("status", default="requested"), col("reason", Text),
                          col("requested_by", String(36)), col("backup_expiry", DateTime(timezone=True)))
audit_events = table("audit_events", col("actor_id", String(36)), col("action"), col("resource_id", String(120)),
                     col("trace_id", String(36)), col("summary", Text))
idempotency = table("idempotency", col("actor_id", String(36)), col("operation"), col("key", String(128)),
                    col("payload_hash", String(64)), col("response", JSON),
                    constraints=(UniqueConstraint("tenant_id", "actor_id", "operation", "key"),))
# Durable queue stores only validated resource IDs, not evidence or actor-supplied tenant payload.
jobs = table("jobs", col("tenant_id", String(36), ForeignKey("tenants.id")), col("kind"), col("resource_id", String(36)),
             col("status", default="queued"), col("attempts", Integer, default=0), col("lease_until", DateTime(timezone=True)),
             col("claim_token", String(36)),
             col("available_at", DateTime(timezone=True), default=now), col("error_code"),
             constraints=(UniqueConstraint("kind", "resource_id"),), tenant=False)
inbox = table("inbox", col("provider"), col("event_id", String(240)), col("payload_hash", String(64)),
              col("status"), col("order_id", String(36)), constraints=(UniqueConstraint("provider", "event_id"),), tenant=False)

form_drafts = table("form_drafts", col("actor_id", String(36), ForeignKey("users.id"), nullable=False),
                    col("kind", nullable=False), col("draft_key", nullable=False), col("version", Integer, nullable=False),
                    col("payload", JSON, nullable=False), col("updated_at", DateTime(timezone=True), nullable=False),
                    col("expires_at", DateTime(timezone=True), nullable=False),
                    constraints=(UniqueConstraint("tenant_id", "actor_id", "kind", "draft_key"),))
ticket_messages = table("ticket_messages", col("ticket_id", String(36), nullable=False),
                        col("actor_id", String(36), ForeignKey("users.id"), nullable=False),
                        col("text", Text, nullable=False), col("visibility", nullable=False),
                        constraints=(ref("ticket_id", "tickets"),))
lifecycle_plans = table("lifecycle_plans", col("request_id", String(36), nullable=False),
                        col("kind", nullable=False), col("manifest", JSON, nullable=False),
                        col("digest", String(64), nullable=False), col("actor_id", String(36), nullable=False),
                        col("expires_at", DateTime(timezone=True), nullable=False),
                        constraints=(ref("request_id", "deletion_requests"),))
erasure_receipts = table("erasure_receipts", col("tenant_ref", String(36), nullable=False),
                         col("plan_digest", String(64), nullable=False, unique=True), col("manifest", JSON, nullable=False),
                         col("status", nullable=False), col("completed_at", DateTime(timezone=True)), tenant=False)
