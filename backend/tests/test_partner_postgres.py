"""Real RLS and concurrent allocation checks on new disposable tenants only."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi import Response
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from kuanguard import models as m, partner_models as p, wallet
from kuanguard.config import settings
from kuanguard.db import add, engine, set_tenant
from kuanguard.security import create_session
from backend.tests.test_postgres_runtime import pg  # noqa: F401 -- shared explicitly local-only fixture


def test_partner_force_rls_parallel_allocation_and_immutable_receipt(pg, monkeypatch):  # noqa: F811 - imported pytest fixture
    monkeypatch.setenv("DATABASE_URL", pg.url.render_as_string(hide_password=False))
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setenv("DEPLOYMENT_SURFACE", "local")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://127.0.0.1:3180")
    settings.cache_clear()
    engine.cache_clear()
    parent, customer, user = str(uuid4()), str(uuid4()), str(uuid4())
    try:
        with pg.begin() as conn:
            for tenant in (parent, customer):
                add(conn, m.tenants, id=tenant, name="QA isolated partner allocation", verified=True)
            add(conn, m.users, id=user, name="QA isolated partner finance", email=user + "@example.invalid")
            add(conn, m.memberships, tenant_id=parent, user_id=user, role="partner_finance")
            add(conn, p.organization_profiles, tenant_id=parent, slug="qa-" + parent, kind="partner", synthetic=True)
            set_tenant(conn, parent, True)
            add(conn, p.tenant_features, parent, code="partner_portal", enabled=True, reason="Isolated concurrent QA")
            link = add(conn, p.partner_customers, parent, customer_tenant_id=customer)
            wallet.grant(conn, parent, 5, "synthetic-concurrency")
            response = Response()
            csrf = create_session(conn, user, parent, response, "testserver", parent)
            cookie = response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
        from kuanguard.api import app
        def allocate(index):
            with TestClient(app) as client:
                client.cookies.set("kg_session", cookie)
                result = client.post(f"/partner/customers/{customer}/credits", json={"quantity": 1, "reason": "Approved isolated concurrency check"},
                    headers={"origin": "http://127.0.0.1:3180", "x-csrf-token": csrf, "idempotency-key": f"allocation-{parent}-{index}"})
                assert result.status_code in {200, 409}, result.text
                return result.status_code
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(allocate, range(12)))
        assert results.count(200) == 5 and results.count(409) == 7
        with pg.begin() as conn:
            set_tenant(conn, parent)
            assert wallet.summary(conn, parent)["available"] == 0 and wallet.allocated(conn, parent) == 5
            assert len(conn.execute(select(p.credit_allocations)).all()) == 5
            set_tenant(conn, customer)
            assert wallet.summary(conn, customer)["available"] == 5
            assert not conn.execute(select(p.partner_customers).where(p.partner_customers.c.id == link["id"])).first()
            assert not conn.execute(select(p.credit_allocations)).first()
        with pg.begin() as conn:
            assert not conn.execute(select(p.credit_allocations)).first()  # Pool context does not leak.
        with pytest.raises(DBAPIError):
            with pg.begin() as conn:
                set_tenant(conn, parent)
                conn.execute(p.credit_allocations.update().where(p.credit_allocations.c.tenant_id == parent).values(quantity=999))
        with pytest.raises(DBAPIError):
            with pg.begin() as conn:
                set_tenant(conn, parent)
                conn.execute(p.audit_contexts.delete().where(p.audit_contexts.c.tenant_id == parent))
    finally:
        with pg.begin() as conn:
            conn.execute(m.tenants.update().where(m.tenants.c.id.in_([parent, customer])).values(status="archived"))
        engine().dispose()
        engine.cache_clear()
        settings.cache_clear()
