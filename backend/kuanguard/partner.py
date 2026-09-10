"""Partner scope, domain resolution and feature availability; no ordering business writer."""
from datetime import timedelta
import hashlib
import hmac
import ipaddress
import re
import secrets
import socket
import ssl
from urllib.parse import urlsplit

from fastapi import HTTPException

from . import models as m, partner_models as p
from .config import settings
from .db import add, all_rows, one, set_tenant
from .security import digest, fail

PARTNER_ROLES = {"partner_admin", "partner_engineer", "partner_reviewer", "partner_sales", "partner_finance"}
DELEGATED_ROLES = {
    "partner_admin": {"pm", "customer_contact", "customer_admin", "campaign_manager", "training_manager"},
    "partner_engineer": {"engineer"}, "partner_reviewer": {"reviewer"},
    "partner_sales": {"pm", "customer_contact"}, "partner_finance": {"finance", "billing_manager"},
}
FEATURES = {"ordering", "reservation", "payments", "delivery", "crm", "va", "wva", "pt", "shc", "source",
            "social_engineering", "training", "partner_portal", "white_label", "custom_domain", "sso", "commission", "referral"}


def host_name(value):
    if not value or any(c in value for c in "\\/@%\r\n\t "):
        fail(400, "INVALID_HOST", "網域格式不正確。")
    try:
        parsed = urlsplit("//" + value)
        if parsed.username or parsed.password or not parsed.hostname:
            raise ValueError()
        parsed.port
        host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        if len(host) > 253 or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split(".")):
            raise ValueError()
        return host
    except (ValueError, UnicodeError):
        fail(400, "INVALID_HOST", "網域格式不正確。")


def platform_origins():
    config = settings()
    return {config.public_site_url, config.customer_app_url, config.internal_app_url,
            config.partner_portal_url, config.central_auth_url} | config.origins


def base_host(host):
    config = settings()
    names = {urlsplit(value).hostname for value in platform_origins()}
    names |= {"api." + config.company_apex_domain, "www." + config.company_apex_domain}
    if config.app_env in {"development", "test"}:
        names |= {"testserver", "127.0.0.1", "localhost"}
    return host in names


def profile(conn, tenant_id):
    return one(conn, p.organization_profiles, None, p.organization_profiles.c.tenant_id == tenant_id)


def active_partner(conn, tenant_id):
    organization = profile(conn, tenant_id)
    tenant = one(conn, m.tenants, None, m.tenants.c.id == tenant_id, m.tenants.c.status == "active")
    if not organization or organization["kind"] != "partner" or not tenant:
        fail(404, "PARTNER_NOT_FOUND", "找不到可使用的合作夥伴。")
    return {**organization, "name": tenant["name"]}


def resolve_partner(conn, host, slug=None):
    host = host_name(host)
    domain = one(conn, p.tenant_domains, None, p.tenant_domains.c.domain == host)
    if domain:
        if domain["status"] != "ACTIVE" or not domain["verified_at"] or domain["tls_status"] != "active":
            fail(404, "DOMAIN_NOT_ACTIVE", "此網域尚未完成驗證與啟用。")
        partner = active_partner(conn, domain["tenant_id"])
        require_feature(conn, partner["tenant_id"], "custom_domain")
        if slug and partner["slug"] != slug:
            fail(403, "PARTNER_DOMAIN_MISMATCH", "網域與合作夥伴不符。")
        return partner
    if not base_host(host):
        fail(404, "DOMAIN_NOT_REGISTERED", "此網域未獲平台授權。")
    if slug:
        found = one(conn, p.organization_profiles, None, p.organization_profiles.c.slug == slug,
                    p.organization_profiles.c.kind == "partner")
        if not found:
            fail(404, "PARTNER_NOT_FOUND", "找不到合作夥伴。")
        return active_partner(conn, found["tenant_id"])
    return None


def valid_origin(conn, origin):
    if origin in platform_origins():
        return True
    try:
        value = urlsplit(origin)
        if value.scheme != "https" or value.username or value.password or value.port or value.path or value.query or value.fragment:
            return False
        domain = one(conn, p.tenant_domains, None, p.tenant_domains.c.domain == value.hostname,
                     p.tenant_domains.c.status == "ACTIVE", p.tenant_domains.c.tls_status == "active")
        return bool(domain and domain["verified_at"] and active_partner(conn, domain["tenant_id"])
                    and feature_values(conn, domain["tenant_id"]).get("custom_domain"))
    except (ValueError, TypeError, HTTPException):
        return False


def link_for(conn, partner_id, customer_id):
    set_tenant(conn, partner_id)
    return one(conn, p.partner_customers, partner_id, p.partner_customers.c.customer_tenant_id == customer_id,
               p.partner_customers.c.active.is_(True))


def effective_access(conn, partner_id, customer_id, user_id):
    active_partner(conn, partner_id)
    if not link_for(conn, partner_id, customer_id):
        fail(403, "CUSTOMER_PARTNER_REVOKED", "客戶合作關係已失效。")
    memberships = all_rows(conn, m.memberships, None, m.memberships.c.tenant_id == partner_id,
                           m.memberships.c.user_id == user_id, m.memberships.c.active.is_(True))
    ceilings = set().union(*(DELEGATED_ROLES.get(row["role"], set()) for row in memberships))
    grant = one(conn, p.partner_customer_access, partner_id, p.partner_customer_access.c.customer_tenant_id == customer_id,
                p.partner_customer_access.c.user_id == user_id, p.partner_customer_access.c.active.is_(True),
                p.partner_customer_access.c.expires_at > m.now())
    if not grant or not set(grant["roles"]).issubset(ceilings) or not grant["roles"]:
        fail(403, "PARTNER_ACCESS_REVOKED", "合作夥伴的個人服務授權已失效。")
    return grant


def scoped_session(conn, session, request, proof):
    """Return delegated roles/projects only after live parent, link and personal-grant checks."""
    host = host_name(request.headers.get("host", ""))
    resolved = resolve_partner(conn, host)
    if proof and proof["host"] != host:
        fail(401, "SESSION_HOST_MISMATCH", "登入工作階段不屬於此網域。")
    if resolved:
        if not proof or proof["partner_id"] != resolved["tenant_id"]:
            fail(403, "SESSION_PARTNER_MISMATCH", "請從此合作夥伴的登入入口重新驗證。")
    elif not base_host(host):
        fail(403, "SESSION_HOST_MISMATCH", "登入來源不符。")
    if proof and proof["partner_id"]:
        partner_id = proof["partner_id"]
        active_partner(conn, partner_id)
        require_feature(conn, partner_id, "partner_portal")
        if proof["delegated"]:
            grant = effective_access(conn, partner_id, session["tenant_id"], session["user_id"])
            set_tenant(conn, session["tenant_id"])
            return set(grant["roles"]), grant["project_ids"], grant
        if session["tenant_id"] != partner_id and not link_for(conn, partner_id, session["tenant_id"]):
            fail(403, "CUSTOMER_PARTNER_REVOKED", "客戶合作關係已失效。")
    set_tenant(conn, session["tenant_id"])
    return None, None, None


def bind_session(conn, token, host, partner_id=None, delegated=False):
    session = one(conn, m.sessions, None, m.sessions.c.token_hash == digest(token))
    if not session:
        raise ValueError("Session must exist before binding")
    return add(conn, p.session_contexts, session_id=session["id"], host=host_name(host),
               partner_id=partner_id, delegated=delegated)


def feature_values(conn, tenant_id):
    set_tenant(conn, tenant_id)
    organization = profile(conn, tenant_id)
    plan = {row["code"]: row["enabled"] for row in all_rows(conn, p.plan_features, tenant_id,
            p.plan_features.c.plan_reference == organization["plan_reference"])} if organization and organization["plan_reference"] else {}
    overrides = {row["code"]: row["enabled"] for row in all_rows(conn, p.tenant_features, tenant_id)}
    return {row["code"]: bool(overrides.get(row["code"], plan.get(row["code"], row["default_enabled"]))) and row["status"] != "planned"
            for row in all_rows(conn, p.feature_definitions)}


def require_feature(conn, tenant_id, code):
    if not feature_values(conn, tenant_id).get(code, False):
        fail(403, "FEATURE_DISABLED", "此企業尚未啟用這項功能。")


def service_feature(conn, tenant_id, service_code):
    code = {"SE": "social_engineering", "TRAINING": "training", "LMS": "training"}.get(service_code, service_code.lower())
    # Legacy fixtures predating catalogue installation keep their prior behavior.
    if one(conn, p.feature_definitions, None, p.feature_definitions.c.code == code):
        require_feature(conn, tenant_id, code)


def require_partner(ctx, *roles):
    ctx.require(*(roles or tuple(PARTNER_ROLES)))
    result = active_partner(ctx.conn, ctx.tenant_id)
    require_feature(ctx.conn, ctx.tenant_id, "partner_portal")
    return result


def require_platform(ctx):
    grant = one(ctx.conn, p.platform_memberships, None, p.platform_memberships.c.user_id == ctx.user_id,
                p.platform_memberships.c.active.is_(True))
    if not grant:
        fail(403, "PLATFORM_ROLE_REQUIRED", "需要明示的平台管理權限。")


def public_branding(conn, partner):
    if not partner:
        return None
    set_tenant(conn, partner["tenant_id"])
    row = one(conn, p.tenant_branding, partner["tenant_id"])
    return {"id": partner["tenant_id"], "slug": partner["slug"], "name": partner["name"], "synthetic": partner["synthetic"],
            "branding": {key: row.get(key) for key in ("company_name", "legal_name", "support_email", "support_phone", "footer",
                                                       "primary_color", "logo_asset_id", "favicon_asset_id", "version")} if row else None}


def new_domain(conn, tenant_id, domain):
    canonical = host_name(domain)
    if domain.lower() != canonical or "." not in canonical or base_host(canonical):
        fail(422, "INVALID_CUSTOM_DOMAIN", "請使用獨立的完整自訂網域，不包含通訊協定或連接埠。")
    if canonical == "qidaigo.com" or canonical.endswith((".qidaigo.com", ".localhost", ".kuanguard.com")) or canonical == "kuanguard.com":
        fail(422, "PROTECTED_DOMAIN", "既有產品與本機保留網域不能加入自訂網域。")
    try:
        ipaddress.ip_address(canonical)
        fail(422, "DOMAIN_REQUIRED", "請使用網域，不能使用 IP 位址。")
    except ValueError:
        pass
    token = secrets.token_urlsafe(32)
    row = add(conn, p.tenant_domains, tenant_id=tenant_id, domain=canonical, verification_hash=digest(token),
              expected_cname=settings().custom_domain_target or None)
    return row, token


def verify_domain_transport(domain, token_hash, target):
    """Actual DNS ownership and verified TLS are separate requirements; no remote mutations."""
    import dns.resolver
    import dns.exception
    if not target:
        fail(503, "CUSTOM_DOMAIN_TARGET_REQUIRED", "維運尚未配置核定的 SaaS 網域目的地。")
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 4
    try:
        records = resolver.resolve("_kuanguard-verification." + domain, "TXT")
        ownership = any(hmac.compare_digest(digest(b"".join(row.strings)), token_hash) for row in records)
        cname = {str(row.target).rstrip(".").lower() for row in resolver.resolve(domain, "CNAME")}
        if not ownership or target.lower().rstrip(".") not in cname:
            return {"ownership": ownership, "routing": False, "tls": False}
        addresses = sorted({str(row.address) for row in resolver.resolve(domain, "A")})
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            return {"ownership": True, "routing": False, "tls": False}
        with socket.create_connection((addresses[0], 443), timeout=4) as transport:
            with ssl.create_default_context().wrap_socket(transport, server_hostname=domain):
                return {"ownership": True, "routing": True, "tls": True}
    except (dns.exception.DNSException, OSError, ssl.SSLError):
        return {"ownership": False, "routing": False, "tls": False}


def default_expiry():
    return m.now() + timedelta(days=90)


def audit_fingerprint(value):
    return hashlib.sha256(value.encode()).hexdigest()[:32]
