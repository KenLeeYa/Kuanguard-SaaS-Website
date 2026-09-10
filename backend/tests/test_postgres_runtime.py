"""Live isolated tenant checks; never reset existing development or production data."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
from uuid import uuid4

from dotenv import dotenv_values
from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError

from kuanguard import models as m, wallet
from kuanguard.db import add, set_tenant
from kuanguard.seed import fixed


@pytest.fixture
def pg():
    url = os.environ.get("PG_TEST_DATABASE_URL") or dotenv_values(".env").get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("Explicit/local development PostgreSQL unavailable")
    if "127.0.0.1:55438" not in url and os.environ.get("PG_TEST_ALLOW_ISOLATED") != "true":
        pytest.skip("Only explicitly isolated PostgreSQL allowed")
    db = create_engine(url, pool_size=8, max_overflow=12, pool_pre_ping=True)
    yield db
    db.dispose()


def test_non_owner_rls_pool_reset_and_cross_tenant_fk(pg):
    with pg.connect() as conn:
        role = conn.execute(text("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")).mappings().one()
        assert role["current_user"] == "kuanguard" and not role["rolsuper"] and not role["rolbypassrls"]
        conn.rollback()
        with conn.begin():
            set_tenant(conn, fixed("tenant-a"))
            assert conn.execute(select(m.projects).where(m.projects.c.id == fixed("project-a"))).first()
            assert not conn.execute(select(m.projects).where(m.projects.c.id == fixed("project-b"))).first()
        with conn.begin():
            assert not conn.execute(select(m.projects)).first()
        try:
            with conn.begin():
                set_tenant(conn, fixed("tenant-a"))
                raise RuntimeError("simulated transaction failure")
        except RuntimeError:
            pass
        with conn.begin():
            assert not conn.execute(select(m.projects)).first()
        with pytest.raises(DBAPIError):
            with conn.begin():
                set_tenant(conn, fixed("tenant-a"))
                add(conn, m.scope_assets, fixed("tenant-a"), batch_id=fixed("batch-b-VA"), asset="cross-tenant-invalid", version=1)
        with conn.begin():
            assert not conn.execute(select(m.projects)).first()


def test_parallel_reserve_consume_no_overspend_and_ledger_immutable(pg):
    tenant = str(uuid4())
    with pg.begin() as conn:
        add(conn, m.tenants, id=tenant, name="QA concurrent wallet isolated tenant", verified=True)
        set_tenant(conn, tenant, mutation=True)
        lot = wallet.grant(conn, tenant, 10, "qa_synthetic")

    def consume(index):
        try:
            with pg.begin() as conn:
                set_tenant(conn, tenant, mutation=True)
                reservation = wallet.reserve(conn, tenant, "training" if index % 2 else "phishing", f"qa-{index}", 1, m.now()+timedelta(hours=1))
                wallet.consume(conn, tenant, reservation["id"])
                wallet.consume(conn, tenant, reservation["id"])
                return "consumed"
        except HTTPException as error:
            assert error.status_code == 409
            return "insufficient"

    with ThreadPoolExecutor(max_workers=12) as pool:
        outcomes = list(pool.map(consume, range(30)))
    assert outcomes.count("consumed") == 10 and outcomes.count("insufficient") == 20
    with pg.begin() as conn:
        set_tenant(conn, tenant)
        balance = wallet.balances(conn, tenant, lot["id"])
        assert balance == {"available": 0, "reserved": 0, "consumed": 10, "expired": 0, "refunded": 0}
    with pytest.raises(DBAPIError):
        with pg.begin() as conn:
            set_tenant(conn, tenant)
            conn.execute(m.wallet_transactions.update().where(m.wallet_transactions.c.tenant_id == tenant).values(available_delta=99))
    with pg.begin() as conn:
        conn.execute(m.tenants.update().where(m.tenants.c.id == tenant).values(status="archived"))
