from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event, insert, select, text
from sqlalchemy.engine import Connection

from .config import settings
from . import models as m


@lru_cache
def engine():
    url = settings().database_url
    if url.startswith("sqlite"):
        Path(".local").mkdir(exist_ok=True)
        result = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(result, "connect")
        def sqlite_settings(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
    else:
        result = create_engine(url, pool_pre_ping=True, pool_size=8, max_overflow=8)
    return result


def set_tenant(conn: Connection, tenant_id: str, mutation=False):
    if conn.dialect.name == "postgresql":
        conn.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": tenant_id})
        if mutation:
            # Tenant-level transaction serialization bounds local throughput; protects ledger and idempotency together.
            conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:tenant, 0))"), {"tenant": tenant_id})


def all_rows(conn, table, tenant=None, *conditions):
    query = select(table)
    if "tenant_id" in table.c and table.name in m.TENANT_TABLES:
        if tenant is None:
            raise ValueError("Explicit verified tenant required")
        query = query.where(table.c.tenant_id == tenant)
    if conditions:
        query = query.where(*conditions)
    return [dict(row) for row in conn.execute(query).mappings()]


def one(conn, table, tenant=None, *conditions):
    rows = all_rows(conn, table, tenant, *conditions)
    return rows[0] if rows else None


def add(conn, table, tenant=None, **values):
    values.setdefault("id", m.uid())
    values.setdefault("created_at", m.now())
    if "tenant_id" in table.c and table.name in m.TENANT_TABLES:
        if tenant is None:
            raise ValueError("Explicit verified tenant required")
        values["tenant_id"] = tenant
    conn.execute(insert(table).values(**values))
    return dict(conn.execute(select(table).where(table.c.id == values["id"])).mappings().one())


def change(conn, table, tenant, resource_id, **values):
    query = table.update().where(table.c.id == resource_id)
    if table.name in m.TENANT_TABLES:
        query = query.where(table.c.tenant_id == tenant)
    conn.execute(query.values(**values))


def aware(value):
    from datetime import timezone
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get_connection():
    with engine().connect() as conn:
        with conn.begin():
            yield conn
