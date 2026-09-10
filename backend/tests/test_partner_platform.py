import base64
from datetime import timedelta
from io import BytesIO
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from kuanguard import models as m, partner_models as p, wallet
from kuanguard.db import add, all_rows, change, one
from kuanguard.partner_setup import seed_partners
from kuanguard.seed import fixed
from kuanguard.security import digest


def post(client, path, body=None, key=None):
    return client.post(path, json=body or {}, headers={"Idempotency-Key": key or str(uuid4())})


@pytest.fixture
def partners(platform):
    with platform["engine"].begin() as conn:
        seed_partners(conn)
    return platform


def enter(client, customer="a"):
    result = post(client, f"/partner/customers/{fixed('tenant-' + customer)}/enter")
    assert result.status_code == 200, result.text
    client.headers["x-csrf-token"] = result.json()["csrf_token"]
    return result.json()


def test_two_partners_and_role_separation(partners):
    admin = partners["login"]("partner-admin-a")
    engineer = partners["login"]("partner-engineer-a")
    other = partners["login"]("partner-admin-b")
    customer = partners["login"]("customer-a")
    assert admin.get("/partner/dashboard").json()["customers"][0]["customer_tenant_id"] == fixed("tenant-a")
    assert other.get("/partner/dashboard").json()["customers"][0]["customer_tenant_id"] == fixed("tenant-b")
    assert engineer.get("/partner/credits").status_code == 403
    assert engineer.get("/partner/branding").status_code == 403
    assert customer.get("/partner/dashboard").status_code == 403
    assert admin.get("/platform/overview").status_code == 403
    assert post(admin, f"/partner/customers/{fixed('tenant-b')}/enter").status_code == 403
    assert admin.get("/partner/workspace/internal/projects").status_code == 403


def test_delegate_reuses_projects_and_revocation_is_live(partners):
    engineer = partners["login"]("partner-engineer-a")
    old = engineer.cookies.get("kg_session")
    enter(engineer)
    assert engineer.cookies.get("kg_session") != old
    me = engineer.get("/auth/me").json()
    assert me["delegated"] and me["tenant"]["id"] == fixed("tenant-a")
    assert me["roles"] == ["engineer"]
    project = engineer.get(f"/partner/workspace/internal/projects/{fixed('project-a')}")
    assert project.status_code == 200, project.text
    assert engineer.get(f"/partner/workspace/internal/projects/{fixed('project-b')}").status_code == 404
    assert post(engineer, "/partner/workspace/internal/publications", {"report_job_id": str(uuid4()), "note": "not a reviewer"}).status_code == 403
    with partners["engine"].begin() as conn:
        tenant = fixed("tenant-partner-a")
        row = one(conn, p.partner_customer_access, tenant, p.partner_customer_access.c.user_id == fixed("partner-engineer-a"))
        change(conn, p.partner_customer_access, tenant, row["id"], active=False)
    assert engineer.get(f"/partner/workspace/internal/projects/{fixed('project-a')}").status_code == 403


@pytest.mark.parametrize("revocation", ["membership", "partner", "customer_link", "project", "feature"])
def test_each_parent_scope_is_rechecked(partners, revocation):
    client = partners["login"]("partner-engineer-a")
    enter(client)
    parent = fixed("tenant-partner-a")
    with partners["engine"].begin() as conn:
        if revocation == "membership":
            row = one(conn, m.memberships, None, m.memberships.c.user_id == fixed("partner-engineer-a"))
            change(conn, m.memberships, None, row["id"], active=False)
        elif revocation == "partner":
            change(conn, m.tenants, None, parent, status="suspended")
        elif revocation == "customer_link":
            row = one(conn, p.partner_customers, parent)
            change(conn, p.partner_customers, parent, row["id"], active=False)
        elif revocation == "project":
            row = one(conn, p.partner_customer_access, parent, p.partner_customer_access.c.user_id == fixed("partner-engineer-a"))
            change(conn, p.partner_customer_access, parent, row["id"], project_ids=[])
        else:
            row = one(conn, p.tenant_features, parent, p.tenant_features.c.code == "partner_portal")
            change(conn, p.tenant_features, parent, row["id"], enabled=False)
    assert client.get(f"/partner/workspace/internal/projects/{fixed('project-a')}").status_code in {403, 404}


def test_personal_grant_cannot_escalate_or_cross_project(partners):
    admin = partners["login"]("partner-admin-a")
    body = {"user_id": fixed("partner-engineer-a"), "roles": ["finance"], "project_ids": [fixed("project-a")],
            "active": True, "expected_version": 1, "expires_at": (m.now() + timedelta(days=1)).isoformat()}
    path = f"/partner/customers/{fixed('tenant-a')}/access"
    assert post(admin, path, body).status_code == 403
    assert post(admin, path, body | {"roles": ["engineer"], "project_ids": [fixed("project-b")]}).status_code == 404
    assert post(admin, path, body | {"roles": ["engineer"], "expected_version": 99}).status_code == 409
    result = post(admin, path, body | {"roles": ["engineer"]})
    assert result.status_code == 200 and result.json()["version"] == 2, result.text


def test_new_project_stays_available_to_delegated_creator(partners):
    admin = partners["login"]("partner-admin-a")
    enter(admin)
    created = post(admin, "/partner/workspace/internal/projects", {"name": "New authorized project", "company_name": "Synthetic A", "year": 2026})
    assert created.status_code == 200, created.text
    assert admin.get("/partner/workspace/internal/projects/" + created.json()["id"]).status_code == 200
    returned = post(admin, "/partner/return")
    assert returned.status_code == 200
    admin.headers["x-csrf-token"] = returned.json()["csrf_token"]
    assert admin.get("/auth/me").json()["roles"] == ["partner_admin"]


def test_allocations_conserve_points_and_replay_without_minting(partners):
    finance = partners["login"]("partner-finance-a")
    path = f"/partner/customers/{fixed('tenant-a')}/credits"
    body = {"quantity": 27, "reason": "approved synthetic allocation"}
    key = str(uuid4())
    before = finance.get("/partner/credits").json()["available"]
    first, replay = post(finance, path, body, key), post(finance, path, body, key)
    assert first.status_code == replay.status_code == 200, first.text
    assert first.json()["id"] == replay.json()["id"]
    after = finance.get("/partner/credits").json()
    assert after["available"] == before - 27 and after["allocated"] == 27
    assert post(finance, path, body | {"quantity": 28}, key).status_code == 409
    assert post(finance, path, body | {"quantity": 1000}).status_code == 409
    assert post(finance, f"/partner/customers/{fixed('tenant-b')}/credits", body).status_code == 404
    customer = partners["login"]("customer-a")
    assert customer.get("/customer/wallet").json()["available"] == 567
    with partners["engine"].begin() as conn:
        tenant = fixed("tenant-partner-a")
        for lot in all_rows(conn, m.point_lots, tenant):
            assert sum(wallet.balances(conn, tenant, lot["id"]).values()) + wallet.allocated(conn, tenant, lot["id"]) == lot["quantity"]


def test_brand_assets_no_html_or_foreign_asset_publication(partners):
    admin = partners["login"]("partner-admin-a")
    other = partners["login"]("partner-admin-b")
    image = BytesIO()
    Image.new("RGB", (20, 20), "green").save(image, "PNG")
    asset = post(admin, "/partner/branding/assets", {"content_base64": base64.b64encode(image.getvalue()).decode()})
    assert asset.status_code == 201, asset.text
    assert admin.get(f"/public/branding/{fixed('tenant-partner-a')}/{asset.json()['id']}").status_code == 404
    values = {"expected_version": 1, "company_name": "Safe Name", "primary_color": "#123456", "logo_asset_id": asset.json()["id"]}
    assert post(other, "/partner/branding", values).status_code == 404
    assert post(admin, "/partner/branding", values | {"company_name": "<script>alert(1)</script>"}).status_code == 422
    assert post(admin, "/partner/branding", values | {"primary_color": "red;url(https://evil.invalid)"}).status_code == 422
    assert post(admin, "/partner/branding", values).status_code == 200
    downloaded = admin.get(f"/public/branding/{fixed('tenant-partner-a')}/{asset.json()['id']}")
    assert downloaded.status_code == 200 and downloaded.headers["content-type"] == "image/png"
    assert post(admin, "/partner/branding/assets", {"content_base64": base64.b64encode(b'<svg onload="alert(1)"/>').decode()}).status_code == 422


@pytest.mark.parametrize("domain", ["https://evil.invalid", "127.0.0.1", "api.kuanguard.com", "app.qidaigo.com", "example..invalid", "bad-.invalid", "evil.invalid:443", "x.localhost", "evil.invalid/path", "evil.invalid@other.invalid"])
def test_domain_syntax_and_reserved_products(partners, domain):
    admin = partners["login"]("partner-admin-a")
    assert post(admin, "/partner/domains", {"domain": domain}).status_code in {400, 422}


def register_active_test_domain(platform, suffix="a"):
    host = f"portal-{suffix}.example.invalid"
    with platform["engine"].begin() as conn:
        row = add(conn, p.tenant_domains, tenant_id=fixed("tenant-partner-" + suffix), domain=host,
                  verification_hash=digest("synthetic-owned-domain"), status="ACTIVE", verified_at=m.now(), tls_status="active")
    return host, row


def handoff(platform, host, user="partner-admin-a", **start_values):
    from kuanguard.api import app
    target = TestClient(app, base_url="https://" + host, follow_redirects=False)
    target.headers["origin"] = "https://" + host
    start = post(target, "/auth/portal/start", {"return_path": "/partner", **start_values})
    assert start.status_code == 200, start.text
    token = parse_qs(urlsplit(start.json()["login_url"]).query)["intent"][0]
    with TestClient(app, base_url="https://auth.kuanguard.com") as central:
        central.headers["origin"] = "https://auth.kuanguard.com"
        completed = post(central, "/auth/portal/dev-complete", {"intent": token, "profile_key": user})
    return target, token, completed


def test_handoff_bound_host_browser_one_use_and_membership(partners):
    host, _ = register_active_test_domain(partners)
    register_active_test_domain(partners, "b")
    target, token, completed = handoff(partners, host)
    assert completed.status_code == 200, completed.text
    callback = urlsplit(completed.json()["redirect"])
    path = callback.path.removeprefix("/api") + "?" + callback.query
    from kuanguard.api import app
    with TestClient(app, base_url="https://" + host) as attacker:
        assert attacker.get(path).status_code == 403  # Code alone is insufficient.
    assert target.get(path, headers={"host": "portal-b.example.invalid", "origin": "https://portal-b.example.invalid"}).status_code == 403
    redeemed = target.get(path)
    assert redeemed.status_code == 303 and redeemed.headers["location"] == "/partner", redeemed.text
    cookie = redeemed.headers.get("set-cookie", "")
    assert "Secure" in cookie and "HttpOnly" in cookie and "Domain=" not in cookie
    assert target.get(path).status_code == 403
    me = target.get("/auth/me")
    assert me.status_code == 200 and me.json()["partner_id"] == fixed("tenant-partner-a"), me.text
    assert target.get("/auth/me", headers={"host": "portal-b.example.invalid", "origin": "https://portal-b.example.invalid"}).status_code in {401, 403}
    assert target.get("/auth/me", headers={"origin": "https://portal-b.example.invalid"}).status_code == 403
    target.close()
    wrong, _, result = handoff(partners, host, "partner-admin-b")
    assert result.status_code == 403
    wrong.close()


def test_pending_domains_and_open_redirects_fail_closed(partners):
    admin = partners["login"]("partner-admin-a")
    registered = post(admin, "/partner/domains", {"domain": "portal.pending.invalid"})
    assert registered.status_code == 201, registered.text
    domain = registered.json()
    assert "verification_hash" not in admin.get("/partner/domains").text
    assert admin.get("/public/portal", headers={"host": "portal.pending.invalid"}).status_code == 404
    assert post(admin, f"/partner/domains/{domain['id']}/verify", {"expected_version": 1}).status_code == 503
    from kuanguard.api import app
    with TestClient(app, base_url="http://127.0.0.1:3180") as browser:
        browser.headers["origin"] = "http://127.0.0.1:3180"
        for path in ["//evil.invalid", "https://evil.invalid", "/%2f%2fevil.invalid", "/partner?tenant=other"]:
            assert post(browser, "/auth/portal/start", {"partner_slug": "megaprotek", "return_path": path}).status_code == 422
        assert post(browser, "/auth/portal/start", {"partner_slug": "megaprotek", "return_path": "/partner", "destination_origin": "https://evil.invalid"}).status_code == 422


def test_cors_verified_allowlist_and_domain_disable(partners):
    host, domain = register_active_test_domain(partners)
    from kuanguard.api import app
    with TestClient(app) as anonymous:
        for origin, status in [("https://" + host, 204), ("https://evil.invalid", 403), ("http://" + host, 403)]:
            response = anonymous.options("/auth/me", headers={"origin": origin, "access-control-request-method": "GET"})
            assert response.status_code == status
            assert response.headers.get("access-control-allow-origin") != "*"
            if status == 204:
                assert response.headers["access-control-allow-origin"] == origin
    admin = partners["login"]("partner-admin-a")
    assert post(admin, f"/partner/domains/{domain['id']}/disable", {"expected_version": 1}).status_code == 200
    assert admin.get("/public/portal", headers={"host": host}).status_code == 404


@pytest.mark.parametrize("revocation", ["feature", "partner"])
def test_custom_origin_loses_cors_on_feature_or_partner_revocation(partners, revocation):
    host, _ = register_active_test_domain(partners)
    tenant = fixed("tenant-partner-a")
    with partners["engine"].begin() as conn:
        if revocation == "feature":
            row = one(conn, p.tenant_features, tenant, p.tenant_features.c.code == "custom_domain")
            change(conn, p.tenant_features, tenant, row["id"], enabled=False)
        else:
            change(conn, m.tenants, None, tenant, status="archived")
    from kuanguard.api import app
    with TestClient(app) as anonymous:
        response = anonymous.options("/auth/me", headers={"origin": "https://" + host, "access-control-request-method": "GET"})
        assert response.status_code == 403
        assert response.headers.get("access-control-allow-origin") is None


def test_feature_plan_precedence_and_planned_activation_denied(partners):
    from kuanguard.partner import feature_values
    owner = partners["login"]("owner-a")
    tenant = fixed("tenant-partner-a")
    with partners["engine"].begin() as conn:
        profile = one(conn, p.organization_profiles, None, p.organization_profiles.c.tenant_id == tenant)
        change(conn, p.organization_profiles, None, profile["id"], plan_reference="partner-plan-v1")
        add(conn, p.plan_features, tenant, plan_reference="partner-plan-v1", code="va", enabled=False)
        assert feature_values(conn, tenant)["va"] is False
    request = {"code": "va", "enabled": True, "expected_version": 0, "reason": "explicit plan override for QA"}
    assert post(owner, f"/platform/organizations/{tenant}/features", request).status_code == 200
    assert post(owner, f"/platform/organizations/{tenant}/features", request).status_code == 409
    with partners["engine"].begin() as conn:
        assert feature_values(conn, tenant)["va"] is True
    assert post(owner, f"/platform/organizations/{tenant}/features", request | {"code": "commission"}).status_code == 409


def test_leads_privacy_idempotency_and_configurable_price(partners):
    owner = partners["login"]("owner-a")
    body = {"kind": "merchant", "name": "Synthetic Person", "company": "Synthetic Shop", "email": "qa@example.invalid",
            "phone": "0912345678", "business_type": "restaurant", "store_count": 1, "message": "test inquiry", "consent": True}
    key = str(uuid4())
    first, second = post(owner, "/public/leads", body, key), post(owner, "/public/leads", body, key)
    assert first.status_code == second.status_code == 201 and first.json()["id"] == second.json()["id"]
    assert post(owner, "/public/leads", body | {"utm": {"email": "qa@example.invalid"}}).status_code == 422
    assert post(owner, "/public/leads", body | {"website": "spam"}).status_code == 422
    assert owner.get("/platform/leads?kind=merchant").json()["total"] == 1
    customer = partners["login"]("customer-a")
    assert customer.get("/platform/leads").status_code == 403
    price = owner.get("/public/commerce").json()
    assert price["pricing"]["unit_amount_minor"] == 100
    update = {"expected_version": price["version"], "unit_amount_minor": 125, "monthly_fee_minor": 0, "buyout_fee_minor": 0,
              "policy_reference": "QA-policy-version-2", "note": "Synthetic pricing projection only"}
    response = post(owner, "/platform/commerce/pricing", update)
    assert response.status_code == 200 and response.json()["source_billing_changed"] is False, response.text
    assert owner.get("/public/commerce").json()["pricing"]["unit_amount_minor"] == 125
    assert owner.get("/public/commerce").json()["pricing"]["charge_enabled"] is False
    assert post(owner, "/public/events", {"event": "merchant_apply", "path": "/"}).status_code == 202
    assert post(owner, "/public/events", {"event": "merchant_apply", "path": "/", "user_id": "private"}).status_code == 422
