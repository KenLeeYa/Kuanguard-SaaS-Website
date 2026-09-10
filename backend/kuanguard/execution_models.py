"""Additive project execution tables; existing tasks and reservations remain authoritative."""
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint

from . import models as m

task_details = m.table("task_details", m.col("task_id", String(36), nullable=False),
    m.col("customer_note", Text, nullable=False, default=""), m.col("internal_note", Text, nullable=False, default=""),
    m.col("version", Integer, nullable=False, default=1),
    constraints=(m.ref("task_id", "tasks"), UniqueConstraint("tenant_id", "task_id"),))
task_dependencies = m.table("task_dependencies", m.col("task_id", String(36), nullable=False),
    m.col("depends_on_id", String(36), nullable=False),
    constraints=(m.ref("task_id", "tasks"), m.ref("depends_on_id", "tasks"),
                 UniqueConstraint("tenant_id", "task_id", "depends_on_id"),
                 CheckConstraint("task_id <> depends_on_id", name="no_self_dependency")))
meeting_decisions = m.table("meeting_decisions", m.col("project_id", String(36), nullable=False),
    m.col("batch_id", String(36)), m.col("publication_id", String(36)), m.col("scope_version", Integer),
    m.col("title", nullable=False), m.col("occurred_at", DateTime(timezone=True), nullable=False),
    m.col("visibility", nullable=False), m.col("customer_text", Text, nullable=False, default=""),
    m.col("internal_note", Text, nullable=False, default=""), m.col("task_ids", JSON, nullable=False),
    m.col("actor_id", String(36), ForeignKey("users.id"), nullable=False),
    constraints=(m.ref("project_id", "projects"), m.ref("batch_id", "batches"), m.ref("publication_id", "publications"),
                 CheckConstraint("visibility IN ('internal', 'customer')", name="decision_visibility")))
project_cost_entries = m.table("project_cost_entries", m.col("project_id", String(36), nullable=False),
    m.col("task_id", String(36)), m.col("phase", nullable=False), m.col("category", nullable=False),
    m.col("minutes", Integer, nullable=False), m.col("cost_minor", Integer), m.col("currency", String(3)),
    m.col("note", Text, nullable=False), m.col("actor_id", String(36), ForeignKey("users.id"), nullable=False),
    m.col("voided_at", DateTime(timezone=True)), m.col("void_reason", Text),
    constraints=(m.ref("project_id", "projects"), m.ref("task_id", "tasks"),
                 CheckConstraint("minutes >= 0 AND (cost_minor IS NULL OR cost_minor >= 0)", name="cost_nonnegative"),
                 CheckConstraint("phase IN ('estimated', 'actual')", name="cost_phase"),
                 CheckConstraint("(cost_minor IS NULL AND currency IS NULL) OR (cost_minor IS NOT NULL AND currency IS NOT NULL)", name="cost_currency")))
dispatch_policies = m.table("dispatch_policies", m.col("travel_buffer_minutes", Integer, nullable=False),
    m.col("reason", Text, nullable=False), m.col("version", Integer, nullable=False, default=1),
    m.col("actor_id", String(36), ForeignKey("users.id"), nullable=False),
    constraints=(UniqueConstraint("tenant_id"), CheckConstraint("travel_buffer_minutes BETWEEN 0 AND 1440", name="buffer_bounds")))
dispatch_qualifications = m.table("dispatch_qualifications", m.col("user_id", String(36), ForeignKey("users.id"), nullable=False),
    m.col("role", nullable=False), m.col("service_code", nullable=False), m.col("valid_until", DateTime(timezone=True)),
    m.col("reason", Text, nullable=False), m.col("active", Boolean, nullable=False, default=True),
    m.col("version", Integer, nullable=False, default=1),
    constraints=(UniqueConstraint("tenant_id", "user_id", "role", "service_code"),
                 CheckConstraint("role IN ('engineer', 'reviewer')", name="qualification_role")))
dispatch_tools = m.table("dispatch_tools", m.col("name", nullable=False), m.col("capacity", Integer, nullable=False),
    m.col("service_codes", JSON, nullable=False), m.col("active", Boolean, nullable=False, default=True),
    m.col("reason", Text, nullable=False), m.col("version", Integer, nullable=False, default=1),
    constraints=(UniqueConstraint("tenant_id", "name"), CheckConstraint("capacity BETWEEN 1 AND 100", name="tool_capacity")))

EXECUTION_TABLES = (task_details, task_dependencies, meeting_decisions, project_cost_entries,
                    dispatch_policies, dispatch_qualifications, dispatch_tools)
