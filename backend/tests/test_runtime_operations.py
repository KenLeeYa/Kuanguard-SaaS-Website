from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from redis import Redis
from redis.exceptions import ConnectionError

from kuanguard import models as m
from kuanguard.db import add
from kuanguard.seed import fixed


def test_operations_health_is_scoped_aggregate_and_read_only(platform):
    client = platform["login"]("pm-a")
    with platform["engine"].begin() as conn:
        add(conn, m.jobs, tenant_id=fixed("tenant-a"), kind="report", resource_id=str(uuid4()),
            status="failed", error_code="private-finding-text")
        add(conn, m.jobs, tenant_id=fixed("tenant-a"), kind="report", resource_id=str(uuid4()),
            status="running", lease_until=m.now()-timedelta(seconds=1))
        add(conn, m.jobs, tenant_id=fixed("tenant-a"), kind="report", resource_id=str(uuid4()),
            available_at=m.now()+timedelta(days=1))
        add(conn, m.jobs, tenant_id=fixed("tenant-b"), kind="report", resource_id=str(uuid4()), status="failed")
        before = list(conn.execute(m.jobs.select()).mappings())
    response = client.get("/internal/operations/health")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["scope"] == "current_tenant" and result["status"] == "attention"
    assert result["jobs"]["report"]["failed"] == 1
    assert result["jobs"]["report"]["expired_leases"] == 1
    assert result["jobs"]["report"]["due_queued"] == 0
    assert result["production_ready"] is False and result["external_alert_delivery"] == "not_configured"
    assert "private-finding-text" not in response.text and fixed("tenant-b") not in response.text
    assert "no-store" in response.headers["cache-control"]
    assert "noindex" in response.headers["x-robots-tag"]
    assert client.get("/internal/operations/health", params={"tenant_id": fixed("tenant-b")}).status_code == 422
    with platform["engine"].begin() as conn:
        assert list(conn.execute(m.jobs.select()).mappings()) == before


@pytest.mark.parametrize("profile", ["customer-a", "learner-a", "engineer-a", "finance-a"])
def test_operations_health_requires_internal_operations_role(platform, profile):
    assert platform["login"](profile).get("/internal/operations/health").status_code == 403


def test_operations_health_denies_anonymous_and_public_surface(platform, monkeypatch):
    from kuanguard.api import app
    from kuanguard.config import settings
    with TestClient(app) as client:
        assert client.get("/internal/operations/health").status_code == 401
    client = platform["login"]("pm-a")
    monkeypatch.setenv("DEPLOYMENT_SURFACE", "public")
    settings.cache_clear()
    assert client.get("/internal/operations/health").status_code == 404
    assert client.get("/partner/workspace/internal/operations/health").status_code == 404


def test_operations_detects_payment_without_point_grant(platform):
    client = platform["login"]("pm-a")
    with platform["engine"].begin() as conn:
        order = add(conn, m.orders, fixed("tenant-a"), points=10, amount_minor=1000)
        add(conn, m.payments, fixed("tenant-a"), order_id=order["id"], provider_ref=str(uuid4()),
            amount_minor=1000, currency="TWD", status="paid")
    response = client.get("/internal/operations/health")
    assert response.status_code == 200, response.text
    assert response.json()["payments"]["grant_mismatches"] == 1
    assert order["id"] not in response.text


def request(peer="192.0.2.1"):
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers={"x-forwarded-for": str(uuid4())})


def test_memory_rate_limit_is_atomic_and_expires(monkeypatch):
    from kuanguard import rate_limits as rates
    monkeypatch.setattr(rates, "settings", lambda: SimpleNamespace(
        app_env="test", redis_url="", rate_limit_backend="memory"))
    clock = [100.0]
    monkeypatch.setattr(rates.time, "monotonic", lambda: clock[0])
    rates._rates.clear()

    def attempt(_):
        try:
            rates.rate_limit(request(), "login", 10)
            return True
        except HTTPException as exc:
            assert exc.status_code == 429
            return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        assert sum(pool.map(attempt, range(50))) == 10
    clock[0] += 61
    assert attempt(0)
    rates._rates.clear()


def test_redis_failure_never_falls_back_to_memory(platform, monkeypatch):
    from kuanguard import rate_limits as rates
    from kuanguard.config import settings
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6388/0")
    settings.cache_clear()

    def unavailable(*args):
        raise ConnectionError("private-provider-connection-string")

    monkeypatch.setattr(rates, "redis_client", unavailable)
    from kuanguard.api import app
    with TestClient(app) as client:
        response = client.post("/auth/dev/login", json={"profile_key": "customer-a"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "RATE_LIMIT_UNAVAILABLE"
    assert "private-provider" not in response.text


def test_rate_limit_http_retry_after_preserves_error_contract(platform, monkeypatch):
    from kuanguard import rate_limits as rates
    from kuanguard.config import settings
    from kuanguard.api import app
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6388/0")
    settings.cache_clear()
    monkeypatch.setattr(rates, "redis_client", lambda _: object())
    monkeypatch.setattr(rates, "redis_window", lambda *args: (0, 1250))
    with TestClient(app) as client:
        response = client.post("/auth/dev/login", json={"profile_key": "customer-a"})
    assert response.status_code == 429 and response.headers["retry-after"] == "2"
    assert response.json()["detail"]["code"] == "RATE_LIMITED"
    assert response.json()["detail"]["trace_id"] == response.headers["x-request-id"]
    assert "no-store" in response.headers["cache-control"]


def test_memory_capacity_refuses_without_evicting_active_clients(monkeypatch):
    from kuanguard import rate_limits as rates
    from collections import deque
    monkeypatch.setattr(rates, "settings", lambda: SimpleNamespace(
        app_env="test", redis_url="", rate_limit_backend="memory"))
    monkeypatch.setattr(rates.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(rates, "_rates", {str(index): deque([99.0]) for index in range(4096)})
    with pytest.raises(HTTPException) as error:
        rates.rate_limit(request(), "login", 10)
    assert error.value.status_code == 503 and len(rates._rates) == 4096


def test_uvicorn_does_not_replace_peer_with_untrusted_forwarded_headers():
    import asyncio
    import httpx
    from uvicorn import Config
    from starlette.responses import JSONResponse
    root = Path(__file__).resolve().parents[2]
    for name in ("compose.yml", "infra/Dockerfile.api", "scripts/start-local.ps1"):
        assert "--no-proxy-headers" in (root / name).read_text(encoding="utf-8")

    async def app(scope, receive, send):
        await JSONResponse({"peer": scope["client"][0], "scheme": scope["scheme"]})(scope, receive, send)

    config = Config(app, proxy_headers=False, lifespan="off", log_config=None)
    config.load()

    async def check():
        transport = httpx.ASGITransport(app=config.loaded_app, client=("127.0.0.1", 12345))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            result = await client.get("/", headers={"X-Forwarded-For": "198.51.100.99", "X-Forwarded-Proto": "https"})
            assert result.json() == {"peer": "127.0.0.1", "scheme": "http"}

    asyncio.run(check())


@pytest.fixture
def isolated_redis():
    url = os.environ.get("REDIS_TEST_URL", "redis://127.0.0.1:6388/0")
    target = urlsplit(url)
    if target.hostname not in {"127.0.0.1", "localhost"} or target.port != 6388:
        pytest.fail("Redis tests require the dedicated loopback port 6388")
    clients = [Redis.from_url(url), Redis.from_url(url)]
    try:
        clients[0].ping()
    except ConnectionError:
        if os.environ.get("REDIS_TEST_URL"):
            pytest.fail("Explicit test Redis is unavailable")
        pytest.skip("Dedicated local Redis unavailable")
    key = "kuanguard:test:rate-limit-test:" + uuid4().hex
    yield clients, key
    clients[0].delete(key)
    for client in clients:
        client.close()


def test_two_redis_clients_share_one_atomic_quota_and_expiry(isolated_redis):
    from kuanguard import rate_limits as rates
    clients, key = isolated_redis

    def attempt(index):
        return rates.redis_window(clients[index % 2], key, 10)[0]

    with ThreadPoolExecutor(max_workers=20) as pool:
        assert sum(pool.map(attempt, range(50))) == 10
    assert clients[0].zcard(key) == 10
    assert 0 < clients[0].pttl(key) <= 60_000
    # Expire every accepted request by its actual Redis clock without waiting a minute.
    seconds, micros = clients[0].time()
    expired_at = seconds * 1000 + micros // 1000 - 60_001
    clients[0].zadd(key, {member: expired_at for member in clients[0].zrange(key, 0, -1)}, xx=True)
    assert rates.redis_window(clients[1], key, 10)[0] == 1
    assert clients[0].zcard(key) == 1


def test_rate_keys_separate_environment_category_and_never_use_forwarded_headers(monkeypatch):
    from kuanguard import rate_limits as rates
    config = SimpleNamespace(app_env="test", redis_url="redis://localhost:6388/0", rate_limit_backend="redis")
    monkeypatch.setattr(rates, "settings", lambda: config)
    keys = []
    monkeypatch.setattr(rates, "redis_client", lambda _: object())
    monkeypatch.setattr(rates, "redis_window", lambda client, key, limit: (keys.append(key) or 1, 0))
    rates.rate_limit(request(), "login", 2)
    rates.rate_limit(request(), "login", 2)
    rates.rate_limit(request(), "quote", 2)
    config.app_env = "development"
    rates.rate_limit(request(), "login", 2)
    assert keys[0] == keys[1] and len(set(keys)) == 3
    assert "192.0.2.1" not in json.dumps(keys)
