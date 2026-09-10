import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def platform(tmp_path, monkeypatch):
    from kuanguard.config import settings
    from kuanguard.db import engine
    from kuanguard import models as m
    from kuanguard.seed import seed
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setenv("AUTH_PROVIDER", "development")
    monkeypatch.setenv("DEPLOYMENT_SURFACE", "local")
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path / "objects"))
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", "local-test-webhook-secret-not-production")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://127.0.0.1:3180")
    settings.cache_clear()
    engine.cache_clear()
    db = engine()
    m.metadata.create_all(db)
    from kuanguard.portfolio import portfolio_metadata
    portfolio_metadata.create_all(db)
    from kuanguard.learning_entitlements import training_metadata
    training_metadata.create_all(db)
    with db.begin() as conn:
        seed(conn)
    from kuanguard.api import app
    from kuanguard.rate_limits import _rates
    _rates.clear()
    clients = []

    def login(profile="customer-a"):
        client = TestClient(app)
        client.headers["origin"] = "http://127.0.0.1:3180"
        response = client.post("/auth/dev/login", json={"profile_key": profile})
        assert response.status_code == 200, response.text
        client.headers["x-csrf-token"] = response.json()["csrf_token"]
        clients.append(client)
        return client

    yield {"login": login, "engine": db, "tmp": tmp_path}
    for client in clients:
        client.close()
    db.dispose()
    engine.cache_clear()
    settings.cache_clear()
