"""Idempotent catalogue installation; synthetic partner fixtures require a separate opt-in."""
import json
from pathlib import Path
import secrets
from . import models as m, partner_models as p, wallet
from .config import settings
from .db import add, all_rows, one, set_tenant
from .partner import FEATURES, DELEGATED_ROLES, default_expiry
from .seed import fixed
from .security import digest

PARTNER_PROFILES = {
    "partner-admin-a": ("partner-a", "三傑科技・示範管理員", ["partner_admin"]),
    "partner-engineer-a": ("partner-a", "三傑科技・示範工程師", ["partner_engineer"]),
    "partner-reviewer-a": ("partner-a", "三傑科技・示範覆核者", ["partner_reviewer"]),
    "partner-sales-a": ("partner-a", "三傑科技・示範業務", ["partner_sales"]),
    "partner-finance-a": ("partner-a", "三傑科技・示範財務", ["partner_finance"]),
    "partner-admin-b": ("partner-b", "第二夥伴・示範管理員", ["partner_admin"]),
}


def install_catalog(conn):
    for code in sorted(FEATURES):
        if not one(conn, p.feature_definitions, None, p.feature_definitions.c.code == code):
            planned = code in {"commission", "referral", "payments", "delivery"}
            add(conn, p.feature_definitions, code=code, default_enabled=code in {
                "va", "wva", "pt", "shc", "source", "social_engineering", "training"},
                status="planned" if planned else "available", description=code)
    if not one(conn, p.product_registry, None, p.product_registry.c.code == "merchant"):
        add(conn, p.product_registry, code="merchant", name="KUANGUARD 商家營運", status="beta",
            entry_url=settings().merchant_entry_url,
            capabilities=[{"code": code, "status": status} for code, status in (
                ("ordering", "available"), ("qr", "available"), ("reservation", "available"),
                ("printing", "available"), ("pos", "beta"), ("crm", "beta"),
                ("multi_store", "available"), ("analytics", "available"),
                ("payments", "planned"), ("delivery", "planned"))],
            pricing={"currency": "TWD", "unit_amount_minor": 100, "unit": "successful_order",
                     "monthly_fee_minor": 0, "buyout_fee_minor": 0, "charge_enabled": False,
                     "excluded_states": ["failed", "cancelled", "refunded"],
                     "policy_reference": "merchant-website-20260910-v1",
                     "note": "公開方案；實際啟用與成功訂單認定依商家合約。金流、設備及第三方費用另計。"},
            source_reference="Stallorder-Platform@d506ff58e538bcca72045302ddca291ec85ab91b")


def seed_partners(conn):
    if settings().app_env not in {"development", "test"}:
        raise RuntimeError("Synthetic partner fixtures prohibited outside development/test")
    install_catalog(conn)
    owner = one(conn, m.users, None, m.users.c.id == fixed("owner-a"))
    if not owner:
        raise RuntimeError("Run the existing development seed first")
    if not one(conn, p.platform_memberships, None, p.platform_memberships.c.user_id == owner["id"]):
        add(conn, p.platform_memberships, user_id=owner["id"])
    for suffix, slug, name in (("a", "megaprotek", "三傑科技（示範設定）"), ("b", "example-partner", "第二合作夥伴（合成資料）")):
        tenant_id = fixed("tenant-partner-" + suffix)
        if not one(conn, m.tenants, None, m.tenants.c.id == tenant_id):
            add(conn, m.tenants, id=tenant_id, name=name, verified=True)
            add(conn, p.organization_profiles, tenant_id=tenant_id, slug=slug, kind="partner", partner_type="SI", synthetic=True)
        set_tenant(conn, tenant_id, True)
        if slug == "megaprotek":
            configuration = Path(__file__).resolve().parents[2] / "config/partners/megaprotek.json"
            if configuration.exists():
                domain = json.loads(configuration.read_text(encoding="utf-8"))["requested_domain"]
                if not one(conn, p.tenant_domains, None, p.tenant_domains.c.domain == domain):
                    add(conn, p.tenant_domains, tenant_id=tenant_id, domain=domain,
                        verification_hash=digest(secrets.token_urlsafe(32)), status="PENDING", tls_status="pending")
        if not one(conn, p.tenant_branding, tenant_id):
            add(conn, p.tenant_branding, tenant_id, company_name=name, primary_color="#0F766E",
                footer="Powered by KUANGUARD · 合成環境")
        for code in ("partner_portal", "white_label", "custom_domain", "sso"):
            if not one(conn, p.tenant_features, tenant_id, p.tenant_features.c.code == code):
                add(conn, p.tenant_features, tenant_id, code=code, enabled=True, reason="Opt-in synthetic fixture")
        if not one(conn, m.wallets, tenant_id):
            wallet.grant(conn, tenant_id, 500, "synthetic-partner-fixture")
        customer_id = fixed("tenant-" + suffix)
        if not one(conn, p.partner_customers, tenant_id, p.partner_customers.c.customer_tenant_id == customer_id):
            add(conn, p.partner_customers, tenant_id, customer_tenant_id=customer_id, originating_partner_id=tenant_id,
                contract_owner=name, service_provider=name)
        for key, (profile_tenant, label, roles) in PARTNER_PROFILES.items():
            if profile_tenant != "partner-" + suffix:
                continue
            if not one(conn, m.users, None, m.users.c.id == fixed(key)):
                add(conn, m.users, id=fixed(key), name=label, email=key + "@example.invalid")
                for role in roles:
                    add(conn, m.memberships, tenant_id=tenant_id, user_id=fixed(key), role=role)
            if not one(conn, p.partner_customer_access, tenant_id, p.partner_customer_access.c.user_id == fixed(key),
                       p.partner_customer_access.c.customer_tenant_id == customer_id):
                set_tenant(conn, customer_id)
                project_ids = [row["id"] for row in all_rows(conn, m.projects, customer_id)]
                set_tenant(conn, tenant_id)
                add(conn, p.partner_customer_access, tenant_id, customer_tenant_id=customer_id, user_id=fixed(key),
                    roles=sorted(set().union(*(DELEGATED_ROLES[role] for role in roles))), project_ids=project_ids,
                    expires_at=default_expiry())
    return {"status": "preserved_or_seeded", "synthetic": True, "external_domains_activated": 0}
