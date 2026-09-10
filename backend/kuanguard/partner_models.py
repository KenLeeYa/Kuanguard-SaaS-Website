"""Additive partner metadata. Existing customer tenant and project keys stay authoritative."""
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint

from . import models as m

# Bootstrap identity/directory records are queried before a tenant is selected.
# No arbitrary-list endpoint exposes session proofs, verification hashes or memberships.
organization_profiles = m.table("organization_profiles", m.col("tenant_id", String(36), ForeignKey("tenants.id"), nullable=False, unique=True),
    m.col("slug", String(80), nullable=False, unique=True), m.col("kind", nullable=False),
    m.col("partner_type"), m.col("plan_reference", String(160)), m.col("synthetic", Boolean, nullable=False, default=False), tenant=False,
    constraints=(CheckConstraint("kind IN ('partner','merchant','customer','platform')", name="organization_kind"),))
tenant_domains = m.table("tenant_domains", m.col("tenant_id", String(36), ForeignKey("tenants.id"), nullable=False),
    m.col("domain", String(253), nullable=False, unique=True), m.col("status", nullable=False, default="PENDING"),
    m.col("verification_hash", String(64), nullable=False), m.col("verified_at", DateTime(timezone=True)),
    m.col("tls_status", nullable=False, default="pending"), m.col("expected_cname", String(253)),
    m.col("is_primary", Boolean, nullable=False, default=False), m.col("version", Integer, nullable=False, default=1),
    m.col("updated_at", DateTime(timezone=True), default=m.now), tenant=False,
    constraints=(CheckConstraint("status IN ('PENDING','VERIFYING','ACTIVE','FAILED','DISABLED')", name="domain_status"),))
session_contexts = m.table("session_contexts", m.col("session_id", String(36), ForeignKey("sessions.id"), nullable=False, unique=True),
    m.col("host", String(253), nullable=False), m.col("partner_id", String(36), ForeignKey("tenants.id")),
    m.col("delegated", Boolean, nullable=False, default=False), tenant=False)
portal_login_intents = m.table("portal_login_intents", m.col("token_hash", String(64), nullable=False, unique=True),
    m.col("partner_id", String(36), ForeignKey("tenants.id")), m.col("tenant_id", String(36), ForeignKey("tenants.id")),
    m.col("destination_origin", String(320), nullable=False), m.col("return_path", String(300), nullable=False),
    m.col("browser_hash", String(64), nullable=False), m.col("expires_at", DateTime(timezone=True), nullable=False),
    m.col("user_id", String(36), ForeignKey("users.id")), m.col("code_hash", String(64), unique=True),
    m.col("authenticated_at", DateTime(timezone=True)), m.col("consumed_at", DateTime(timezone=True)), tenant=False)
portal_oidc_links = m.table("portal_oidc_links", m.col("oidc_state_id", String(36), ForeignKey("oidc_states.id"), nullable=False, unique=True),
    m.col("intent_id", String(36), ForeignKey("portal_login_intents.id"), nullable=False), tenant=False)
platform_memberships = m.table("platform_memberships", m.col("user_id", String(36), ForeignKey("users.id"), nullable=False, unique=True),
    m.col("active", Boolean, nullable=False, default=True), tenant=False)
product_registry = m.table("product_registry", m.col("code", nullable=False, unique=True), m.col("name", nullable=False),
    m.col("entry_url", String(500)), m.col("status", nullable=False, default="planned"),
    m.col("capabilities", JSON, nullable=False), m.col("pricing", JSON, nullable=False),
    m.col("source_reference", String(500)), m.col("version", Integer, nullable=False, default=1), tenant=False)
platform_leads = m.table("platform_leads", m.col("kind", nullable=False), m.col("name", nullable=False),
    m.col("company"), m.col("phone", String(40)), m.col("email", String(254), nullable=False),
    m.col("business_type"), m.col("store_count", Integer), m.col("message", Text), m.col("source", String(160)),
    m.col("utm", JSON), m.col("status", default="new"), m.col("assignee", String(36), ForeignKey("users.id")),
    m.col("submission_hash", String(64), nullable=False, unique=True), m.col("payload_hash", String(64), nullable=False), tenant=False)
analytics_daily = m.table("analytics_daily", m.col("day", String(10), nullable=False), m.col("event", String(40), nullable=False),
    m.col("path", String(160), nullable=False), m.col("count", Integer, nullable=False, default=1), tenant=False,
    constraints=(UniqueConstraint("day", "event", "path"),))
feature_definitions = m.table("feature_definitions", m.col("code", nullable=False, unique=True),
    m.col("default_enabled", Boolean, nullable=False, default=False), m.col("status", default="available"),
    m.col("description", Text), tenant=False)

tenant_branding = m.table("tenant_branding", m.col("company_name", nullable=False), m.col("legal_name"),
    m.col("support_email", String(254)), m.col("support_phone", String(40)), m.col("footer", String(300)),
    m.col("primary_color", String(7), default="#0F766E"), m.col("logo_asset_id", String(36)),
    m.col("favicon_asset_id", String(36)), m.col("version", Integer, nullable=False, default=1),
    constraints=(UniqueConstraint("tenant_id"),))
branding_assets = m.table("branding_assets", m.col("object_key", String(500), nullable=False),
    m.col("sha256", String(64), nullable=False), m.col("media_type", String(80), nullable=False),
    m.col("size", Integer, nullable=False), constraints=(UniqueConstraint("tenant_id", "sha256"),))
partner_customers = m.table("partner_customers", m.col("customer_tenant_id", String(36), ForeignKey("tenants.id"), nullable=False, unique=True),
    m.col("customer_source", nullable=False, default="PARTNER"), m.col("originating_partner_id", String(36), ForeignKey("tenants.id")),
    m.col("account_manager_id", String(36), ForeignKey("users.id")), m.col("contract_owner", String(160)),
    m.col("service_provider", String(160)), m.col("active", Boolean, nullable=False, default=True),
    m.col("version", Integer, nullable=False, default=1),
    constraints=(CheckConstraint("tenant_id <> customer_tenant_id", name="different_customer"),))
partner_customer_access = m.table("partner_customer_access", m.col("customer_tenant_id", String(36), ForeignKey("tenants.id"), nullable=False),
    m.col("user_id", String(36), ForeignKey("users.id"), nullable=False), m.col("roles", JSON, nullable=False),
    m.col("project_ids", JSON, nullable=False), m.col("active", Boolean, nullable=False, default=True),
    m.col("expires_at", DateTime(timezone=True), nullable=False), m.col("version", Integer, nullable=False, default=1),
    constraints=(UniqueConstraint("tenant_id", "customer_tenant_id", "user_id"),))
tenant_features = m.table("tenant_features", m.col("code", nullable=False), m.col("enabled", Boolean, nullable=False),
    m.col("version", Integer, nullable=False, default=1), m.col("reason", Text, nullable=False),
    constraints=(UniqueConstraint("tenant_id", "code"),))
plan_features = m.table("plan_features", m.col("plan_reference", String(160), nullable=False), m.col("code", nullable=False),
    m.col("enabled", Boolean, nullable=False), constraints=(UniqueConstraint("tenant_id", "plan_reference", "code"),))
partner_commission_rules = m.table("partner_commission_rules", m.col("model", nullable=False),
    m.col("basis", String(160), nullable=False), m.col("amount_minor", Integer), m.col("basis_points", Integer),
    m.col("currency", String(3)), m.col("version", Integer, nullable=False, default=1), m.col("active", Boolean, default=False),
    constraints=(CheckConstraint("model IN ('percentage','fixed_fee','per_customer','per_service','recurring','referral')", name="commission_model"),
                 CheckConstraint("amount_minor IS NULL OR amount_minor >= 0", name="commission_amount"),
                 CheckConstraint("basis_points IS NULL OR (basis_points >= 0 AND basis_points <= 10000)", name="commission_percent")))
partner_settlements = m.table("partner_settlements", m.col("period", String(30), nullable=False),
    m.col("currency", String(3), nullable=False), m.col("amount_minor", Integer, nullable=False),
    m.col("status", default="draft"), constraints=(UniqueConstraint("tenant_id", "period", "currency"),))
partner_commission_records = m.table("partner_commission_records", m.col("rule_id", String(36), nullable=False),
    m.col("settlement_id", String(36)), m.col("source_reference", String(160), nullable=False),
    m.col("amount_minor", Integer, nullable=False), m.col("currency", String(3), nullable=False),
    constraints=(m.ref("rule_id", "partner_commission_rules"), m.ref("settlement_id", "partner_settlements"),
                 UniqueConstraint("tenant_id", "source_reference")))
credit_allocations = m.table("credit_allocations", m.col("customer_tenant_id", String(36), ForeignKey("tenants.id"), nullable=False),
    m.col("quantity", Integer, nullable=False), m.col("source_lots", JSON, nullable=False), m.col("destination_lots", JSON, nullable=False),
    m.col("actor_id", String(36), ForeignKey("users.id")), m.col("reason", Text, nullable=False),
    constraints=(CheckConstraint("quantity > 0", name="allocation_positive"),))
audit_contexts = m.table("audit_contexts", m.col("audit_event_id", String(36), nullable=False),
    m.col("partner_id", String(36)), m.col("roles", JSON, nullable=False), m.col("ip_hash", String(64)),
    m.col("user_agent", String(300)), m.col("details", JSON, nullable=False),
    constraints=(m.ref("audit_event_id", "audit_events"), UniqueConstraint("tenant_id", "audit_event_id")))
tenant_identity_providers = m.table("tenant_identity_providers", m.col("provider", nullable=False),
    m.col("protocol", nullable=False), m.col("enabled", Boolean, nullable=False, default=False),
    m.col("configuration_reference", String(160)), m.col("version", Integer, nullable=False, default=1),
    constraints=(UniqueConstraint("tenant_id", "provider"), CheckConstraint("protocol IN ('oidc','saml')", name="identity_protocol")))

PARTNER_TABLES = (organization_profiles, tenant_domains, session_contexts, portal_login_intents, portal_oidc_links,
    platform_memberships, product_registry, platform_leads, analytics_daily, feature_definitions, tenant_branding,
    branding_assets, partner_customers, partner_customer_access, tenant_features, plan_features,
    partner_commission_rules, partner_settlements, partner_commission_records, credit_allocations, audit_contexts, tenant_identity_providers)
IMMUTABLE_PARTNER_TABLES = (partner_commission_records, credit_allocations, audit_contexts)
