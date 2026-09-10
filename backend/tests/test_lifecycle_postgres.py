"""Erase only a newly created disposable tenant; preserve every existing tenant."""
from datetime import timedelta
import os
from uuid import uuid4

from dotenv import dotenv_values
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError

from kuanguard import models as m
from kuanguard.db import add, one, set_tenant
from kuanguard.lifecycle import canonical, erasure_manifest, execute_erasure
from kuanguard.security import digest
from kuanguard.seed import fixed


def test_postgres_scoped_erasure_preserves_other_rows_and_immutable_triggers(tmp_path, monkeypatch):
    from kuanguard.config import settings
    values = dotenv_values(".env")
    url = os.environ.get("MIGRATION_DATABASE_URL") or values.get("MIGRATION_DATABASE_URL", "")
    runtime_url = os.environ.get("PG_TEST_DATABASE_URL") or values.get("DATABASE_URL", "")
    if not url.startswith("postgresql") or ("127.0.0.1:55438" not in url and os.environ.get("PG_TEST_ALLOW_ISOLATED") != "true"):
        pytest.skip("Explicit isolated PostgreSQL migration role required")
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path / "erasure-objects"))
    settings.cache_clear()
    admin, runtime = create_engine(url), create_engine(runtime_url)
    tenant = str(uuid4())
    try:
        with admin.begin() as conn:
            baseline = dict(conn.execute(select(m.projects).where(m.projects.c.id == fixed("project-a"))).mappings().one())
            add(conn, m.tenants, id=tenant, name="QA disposable erasure", status="offboarding")
            set_tenant(conn, tenant, mutation=True)
            add(conn, m.wallets, tenant, frozen=True)
            request = add(conn, m.deletion_requests, tenant, data_class="tenant_offboard", status="erasure_approved",
                          reason="isolated synthetic erasure test", requested_by="qa-test", backup_expiry=m.now()-timedelta(seconds=1))
            add(conn, m.retention_policies, tenant, data_class="tenant_all", days=0, version=1, approved=True)
            add(conn, m.audit_events, tenant, actor_id="qa-test", action="synthetic", resource_id=tenant, summary="synthetic disposable")
            manifest = erasure_manifest(conn, tenant, request["id"])
        with pytest.raises(DBAPIError), runtime.begin() as conn:
            set_tenant(conn, tenant)
            conn.execute(m.erasure_receipts.select())
        result = execute_erasure(admin, manifest, digest(canonical(manifest)))
        assert result["status"] == "erased"
        assert execute_erasure(admin, manifest, digest(canonical(manifest))) == result
        with admin.begin() as conn:
            assert dict(conn.execute(select(m.projects).where(m.projects.c.id == fixed("project-a"))).mappings().one()) == baseline
            assert not one(conn, m.audit_events, tenant)
            triggers = conn.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgname='immutable_record'")).scalars().all()
            assert triggers and set(triggers) == {"O"}
    finally:
        admin.dispose()
        runtime.dispose()
        settings.cache_clear()
