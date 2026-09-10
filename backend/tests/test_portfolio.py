from datetime import timedelta
import hashlib
import hmac
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import jwt
from pydantic import ValidationError
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool

from kuanguard import models as m
from kuanguard.db import add, get_connection
from kuanguard.portfolio import (ConnectorError, PortfolioSettings, credential_binding, disable_connector,
    fetch_qidaigo, local_summary, portfolio_metadata, portfolio_overview, connectors, persist_refresh,
    prune_expired_projections, read_qidaigo)
from kuanguard import portfolio_routes
from kuanguard.security import Context, digest

TOKEN_KEY = "test-only-readonly-token-key-00000000000000000"
RESPONSE_KEY = "test-only-response-key-0000000000000000000000"


def configured(now, **claims_changes):
    claims = {"iss": "qidaigo-summary", "aud": "kuanguard-portfolio", "sub": "portfolio-readonly", "jti": "test-grant-1",
              "iat": int(now.timestamp()), "exp": int((now + timedelta(hours=1)).timestamp()), "product": "qidaigo",
              "environment": "test", "scope": "portfolio.summary.read", "tenant_scope": "approved-owner-aggregate", **claims_changes}
    return PortfolioSettings(_env_file=None, environment="test", qidaigo_url="https://summary.qidaigo.example/api/portfolio/summary",
        qidaigo_allowed_hosts="summary.qidaigo.example", qidaigo_tenant_scope="approved-owner-aggregate", qidaigo_owner_tenant_id="tenant-a",
        qidaigo_token=jwt.encode(claims, TOKEN_KEY, algorithm="HS256"), qidaigo_token_key=TOKEN_KEY, qidaigo_response_key=RESPONSE_KEY,
        cache_ttl_seconds=30, source_max_age_seconds=120)


def source_data(now):
    return {"schema_version": "portfolio.summary/1", "product": "qidaigo", "environment": "test", "scope": "portfolio.summary.read",
            "tenant_scope": "approved-owner-aggregate", "grant_id": "test-grant-1", "source_at": now.isoformat(), "complete": True,
            "synthetic": True, "metrics": [{"key": key, "value": value, "unit": "minor_currency", "currency": "TWD", "tax_basis": "inclusive",
                "definition_version": f"qidaigo.{key}/1", "period_start": (now - timedelta(days=1)).isoformat(), "period_end": now.isoformat(),
                "timezone": "Asia/Taipei", "measurement": "flow", "verified": True} for key, value in
                [("gmv", 800000), ("platform_fees_accrued", 8000), ("platform_fees_received", 6000), ("refunds", 10000)]],
            "health": "healthy", "tasks_open": 3, "tasks_overdue": 1}


def response_transport(data, now, *, signature_valid=True, status=200):
    def respond(request):
        if status != 200:
            return httpx.Response(status)
        body = json.dumps(data, ensure_ascii=False).encode()
        timestamp = str(int(now.timestamp()))
        message = timestamp.encode() + b"\n" + request.headers["x-portfolio-nonce"].encode() + b"\n" + body
        signature = hmac.new(RESPONSE_KEY.encode(), message, hashlib.sha256).hexdigest() if signature_valid else "invalid"
        return httpx.Response(200, content=body, headers={"content-type": "application/json", "x-portfolio-timestamp": timestamp, "x-portfolio-signature": signature})
    return httpx.MockTransport(respond)


@pytest.fixture
def db_context():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    m.metadata.create_all(engine)
    portfolio_metadata.create_all(engine)
    with engine.connect() as conn:
        with conn.begin():
            for tenant_id in ("tenant-a", "tenant-b"):
                add(conn, m.tenants, id=tenant_id, name=f"PRIVATE {tenant_id}", verified=True, status="active")
            user = add(conn, m.users, id="owner-user", name="Private Owner", email="owner@example.test", active=True)
            add(conn, m.memberships, tenant_id="tenant-a", user_id=user["id"], role="portfolio_owner", active=True)
            add(conn, m.sessions, tenant_id="tenant-a", user_id=user["id"], token_hash=digest("owner-session"), csrf_token="csrf-owner", expires_at=m.now() + timedelta(hours=1), revoked=False)
            tenant = dict(conn.execute(select(m.tenants).where(m.tenants.c.id == "tenant-a")).mappings().one())
            for tenant_id, value in (("tenant-a", 10000), ("tenant-b", 90000)):
                quote = add(conn, m.quotes, tenant_id, family_id=tenant_id + "-quote", version=1, title="PRIVATE CUSTOMER QUOTE", amount_minor=value,
                            currency="TWD", services=["VA"], valid_until=m.now() + timedelta(days=30), status="accepted")
                add(conn, m.contracts, tenant_id, quote_id=quote["id"], title="PRIVATE CUSTOMER CONTRACT", amount_minor=value, status="active")
                order = add(conn, m.orders, tenant_id, points=value // 100, amount_minor=value, currency="TWD", status="paid")
                add(conn, m.payments, tenant_id, order_id=order["id"], provider_ref=tenant_id + "-test-paid", amount_minor=value, currency="TWD", status="paid")
                add(conn, m.point_lots, tenant_id, order_id=order["id"], source="paid_sandbox", quantity=value // 100,
                    paid_amount_minor=value, expires_at=m.now() + timedelta(days=30))
                add(conn, m.tasks, tenant_id, title="PRIVATE TASK TITLE", status="open", due_at=m.now() - timedelta(days=1))
            ctx = Context(conn, "tenant-a", user["id"], user, tenant, {"portfolio_owner"}, "csrf-owner", "portfolio-test-trace")
            yield ctx
    engine.dispose()


def test_not_configured_is_disconnected_without_zero_revenue(db_context):
    config = PortfolioSettings(_env_file=None, environment="test")
    output = portfolio_overview(db_context, config)
    assert output["combined_financial_total"] is None
    qidaigo = output["items"][1]
    assert qidaigo["status"] == "disconnected" and qidaigo["metrics"] == []
    assert qidaigo["tasks"]["open"] is None and qidaigo["health"]["status"] == "unknown"
    local = output["items"][0]
    by_key = {metric["key"]: metric for metric in local["metrics"]}
    assert by_key["contracted_amount"]["value"] == 10000
    assert by_key["points_purchase_cash"]["value"] == 10000
    assert by_key["points_purchased"]["value"] == 100
    assert by_key["cash_received"]["value"] is None
    assert by_key["accounts_receivable"]["value"] is None
    assert local["tasks"]["open"] == 1
    assert "PRIVATE" not in json.dumps(output)
    assert "findings" not in output and "orders" not in output


def test_portfolio_owner_role_does_not_imply_project_or_findings_access(db_context):
    assert db_context.project_ids() == []
    db_context.roles = {"finance", "pm", "engineer", "reviewer"}
    with pytest.raises(Exception) as denied:
        portfolio_overview(db_context, PortfolioSettings(_env_file=None))
    assert denied.value.status_code == 403


@pytest.mark.parametrize("changes", [{"product": "kuanguard"}, {"environment": "production"}, {"scope": "admin.write"},
                                      {"tenant_scope": "other-product-scope"}, {"sub": "admin"}])
def test_swapped_product_environment_scope_credentials_rejected_before_network(changes):
    now = m.now()
    config = configured(now, **changes)
    calls = []
    with pytest.raises(ConnectorError):
        fetch_qidaigo(config, "tenant-a", now=now, transport=httpx.MockTransport(lambda request: calls.append(request)))
    assert calls == []


def test_credential_expiry_and_other_owner_tenant_rejected():
    now = m.now()
    with pytest.raises(ConnectorError, match="EXPIRED"):
        credential_binding(configured(now, exp=int((now - timedelta(seconds=1)).timestamp())), "tenant-a", now)
    with pytest.raises(ConnectorError, match="SCOPE_NOT_GRANTED"):
        credential_binding(configured(now), "tenant-b", now)


@pytest.mark.parametrize("url", ["http://summary.qidaigo.example/data", "https://other.example/data", "https://127.0.0.1/data",
                                "https://summary.qidaigo.example/data?token=private", "https://user:pass@summary.qidaigo.example/data"])
def test_url_boundary_rejects_unapproved_origin_userinfo_query_and_private_addresses(url):
    with pytest.raises(ValidationError):
        PortfolioSettings(_env_file=None, qidaigo_url=url, qidaigo_allowed_hosts="summary.qidaigo.example,127.0.0.1")


def test_signed_projection_verified_and_financial_meanings_stay_separate():
    now = m.now()
    result, binding = fetch_qidaigo(configured(now), "tenant-a", now=now, transport=response_transport(source_data(now), now))
    assert result["status"] == "connected" and len(binding) == 64
    metrics = {metric["key"]: metric for metric in result["metrics"]}
    assert metrics["gmv"]["value"] == 800000
    assert metrics["platform_fees_received"]["value"] == 6000
    assert "revenue" not in result and "total" not in result
    assert metrics["gmv"]["definition_version"] != metrics["platform_fees_received"]["definition_version"]


@pytest.mark.parametrize("change", ["product", "environment", "scope", "metric", "raw_record", "tax_unit", "duplicate", "incomplete", "timezone"])
def test_signed_but_mismatched_source_schema_or_metrics_fail_closed(change):
    now = m.now()
    data = source_data(now)
    if change == "product":
        data["product"] = "kuanguard"
    if change == "environment":
        data["environment"] = "production"
    if change == "scope":
        data["tenant_scope"] = "wrong-tenant"
    if change == "metric":
        data["metrics"][0]["definition_version"] = "qidaigo.revenue/1"
    if change == "raw_record":
        data["pendingPayments"] = [{"name": "private customer"}]
    if change == "tax_unit":
        data["metrics"][0]["unit"] = "points"
    if change == "duplicate":
        data["metrics"].append(data["metrics"][0])
    if change == "incomplete":
        data["metrics"] = data["metrics"][:1]
    if change == "timezone":
        data["metrics"][0]["timezone"] = "Unknown/Invalid"
    with pytest.raises(ConnectorError):
        fetch_qidaigo(configured(now), "tenant-a", now=now, transport=response_transport(data, now))


def test_bad_signature_and_stale_source_are_not_zero_or_healthy():
    now = m.now()
    with pytest.raises(ConnectorError, match="SIGNATURE_INVALID"):
        fetch_qidaigo(configured(now), "tenant-a", now=now, transport=response_transport(source_data(now), now, signature_valid=False))
    old = source_data(now - timedelta(minutes=5))
    with pytest.raises(ConnectorError) as stale:
        fetch_qidaigo(configured(now), "tenant-a", now=now, transport=response_transport(old, now))
    assert stale.value.state == "stale"


def test_timeout_does_not_block_kuanguard_and_revocation_clears_cache(db_context):
    now = m.now()
    config = configured(now)
    def timeout(_request):
        raise httpx.ReadTimeout("synthetic source timeout")
    output = persist_refresh(db_context, "qidaigo", config, now=now, transport=httpx.MockTransport(timeout))
    assert output["status"] == "error" and output["metrics"] == []
    assert local_summary(db_context, config)["status"] == "connected"
    persist_refresh(db_context, "qidaigo", config, now=now, transport=response_transport(source_data(now), now))
    assert read_qidaigo(db_context, config, now)["status"] == "connected"
    disable_connector(db_context, "qidaigo", config)
    assert read_qidaigo(db_context, config, now)["status"] == "revoked"
    row = dict(db_context.conn.execute(select(connectors)).mappings().one())
    assert row["projection"] is None and row["expires_at"] is None
    assert persist_refresh(db_context, "qidaigo", config, now=now)["status"] == "revoked"


def test_expired_projection_no_longer_displays_numbers_and_ttl_prune_clears_it(db_context):
    now = m.now()
    config = configured(now)
    persist_refresh(db_context, "qidaigo", config, now=now, transport=response_transport(source_data(now), now))
    stale = read_qidaigo(db_context, config, now + timedelta(seconds=31))
    assert stale["status"] == "stale" and stale["metrics"] == []
    assert prune_expired_projections(db_context.conn, "tenant-b", now + timedelta(seconds=31)) == 0
    assert prune_expired_projections(db_context.conn, "tenant-a", now + timedelta(seconds=31)) == 1
    assert db_context.conn.execute(select(connectors.c.projection)).scalar_one() is None


def test_revoked_source_credentials_clear_last_successful_projection(db_context):
    now = m.now()
    config = configured(now)
    persist_refresh(db_context, "qidaigo", config, now=now, transport=response_transport(source_data(now), now))
    revoked = persist_refresh(db_context, "qidaigo", config, now=now, transport=response_transport({}, now, status=403))
    assert revoked["status"] == "revoked" and revoked["metrics"] == []
    assert db_context.conn.execute(select(connectors.c.projection)).scalar_one() is None


def test_route_csrf_owner_guard_and_refresh_replay_does_not_expose_revoked_projection(db_context, monkeypatch):
    from kuanguard import portfolio
    now = m.now()
    config = configured(now)
    monkeypatch.setattr(portfolio_routes, "portfolio_settings", lambda: config)
    original_fetch = portfolio.fetch_qidaigo
    calls = []
    def fake_fetch(config, tenant_id, **kwargs):
        calls.append(tenant_id)
        return original_fetch(config, tenant_id, now=now, transport=response_transport(source_data(now), now))
    monkeypatch.setattr(portfolio, "fetch_qidaigo", fake_fetch)
    app = FastAPI()
    app.include_router(portfolio_routes.router)
    @app.middleware("http")
    async def trace(request, call_next):
        request.state.trace_id = "portfolio-api-test"
        return await call_next(request)
    def connection():
        yield db_context.conn
    app.dependency_overrides[get_connection] = connection
    client = TestClient(app)
    assert client.get("/internal/portfolio").status_code == 401
    client.cookies.set("kg_session", "owner-session")
    assert client.get("/internal/portfolio").status_code == 200
    assert client.get("/internal/portfolio?tenant_id=tenant-b").status_code == 422
    assert client.post("/internal/portfolio/connectors/qidaigo/refresh").status_code == 403
    headers = {"origin": "http://127.0.0.1:3180", "x-csrf-token": "csrf-owner", "idempotency-key": "refresh-1"}
    first = client.post("/internal/portfolio/connectors/qidaigo/refresh", headers=headers)
    assert first.status_code == 200 and first.json()["status"] == "connected"
    assert client.post("/internal/portfolio/connectors/qidaigo/refresh", headers=headers).json()["status"] == "connected"
    assert calls == ["tenant-a"]
    assert client.post("/internal/portfolio/connectors/qidaigo/refresh", headers={**headers, "idempotency-key": "bad-body"},
                       json={"url": "https://other.example", "scope": "admin"}).status_code == 422
    assert client.post("/internal/portfolio/connectors/qidaigo/refresh?tenant_id=tenant-b", headers={**headers, "idempotency-key": "bad-scope"}).status_code == 422
    disabled = client.post("/internal/portfolio/connectors/qidaigo/disable", headers={**headers, "idempotency-key": "disable-1"})
    assert disabled.json()["status"] == "revoked"
    replay = client.post("/internal/portfolio/connectors/qidaigo/refresh", headers=headers)
    assert replay.json()["status"] == "revoked" and replay.json()["metrics"] == []
    stored = db_context.conn.execute(select(m.idempotency.c.response).where(m.idempotency.c.operation == "portfolio.refresh.qidaigo")).scalar_one()
    assert set(stored) == {"product", "status"}
    db_context.conn.execute(m.memberships.update().where(m.memberships.c.user_id == "owner-user").values(role="engineer"))
    assert client.get("/internal/portfolio").status_code == 403


def test_explicit_reactivation_requires_new_qidaigo_grant(db_context):
    now = m.now()
    config = configured(now)
    persist_refresh(db_context, "qidaigo", config, now=now, transport=response_transport(source_data(now), now))
    disable_connector(db_context, "qidaigo", config)
    assert persist_refresh(db_context, "qidaigo", config, now=now)["status"] == "revoked"
    renewed = configured(now, jti="new-approved-grant")
    data = source_data(now)
    data["grant_id"] = "new-approved-grant"
    assert persist_refresh(db_context, "qidaigo", renewed, now=now, transport=response_transport(data, now))["status"] == "connected"


def test_redirect_or_oversized_response_cannot_expand_source_request():
    now = m.now()
    requests = []
    def redirect(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "https://evil.example/"})
    with pytest.raises(ConnectorError, match="HTTP_ERROR"):
        fetch_qidaigo(configured(now), "tenant-a", now=now, transport=httpx.MockTransport(redirect))
    assert len(requests) == 1 and requests[0].method == "GET" and requests[0].content == b""
    with pytest.raises(ConnectorError, match="TOO_LARGE"):
        fetch_qidaigo(configured(now), "tenant-a", now=now, transport=httpx.MockTransport(lambda _: httpx.Response(
            200, content=b"x" * (128 * 1024 + 1), headers={"content-type": "application/json"})))
