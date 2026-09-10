import base64
from datetime import timedelta
import hashlib
import hmac
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Response
from fastapi.testclient import TestClient
import jwt
import pytest

from kuanguard import models as m, partner_models as p
from kuanguard.config import settings
from kuanguard.db import add, all_rows, change, one
from kuanguard.partner_setup import seed_partners
from kuanguard.security import create_session, digest
from kuanguard.seed import fixed
from backend.tests.test_partner_platform import register_active_test_domain, post


@pytest.mark.parametrize("bad_claim", [None, "nonce", "aud", "iss", "expired"])
def test_oidc_pkce_state_claims_and_one_time_callback(platform, monkeypatch, bad_claim):
    import httpx
    from kuanguard.api import app
    with platform["engine"].begin() as conn:
        seed_partners(conn)
        change(conn, m.users, None, fixed("partner-admin-a"), oidc_subject="https://idp.example.invalid|operator-subject")
    host, _ = register_active_test_domain(platform)
    for key, value in {"AUTH_PROVIDER": "oidc", "OIDC_ISSUER": "https://idp.example.invalid", "OIDC_CLIENT_ID": "portal-client",
                       "OIDC_CLIENT_SECRET": "synthetic-provider-secret", "OIDC_REDIRECT_URI": "https://auth.kuanguard.com/api/auth/oidc/callback"}.items():
        monkeypatch.setenv(key, value)
    settings.cache_clear()
    metadata = {"issuer": "https://idp.example.invalid", "authorization_endpoint": "https://idp.example.invalid/authorize",
                "token_endpoint": "https://idp.example.invalid/token", "jwks_uri": "https://idp.example.invalid/jwks"}
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: SimpleNamespace(json=lambda: metadata))
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(jwt, "PyJWKClient", lambda *args, **kwargs: SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=signing_key.public_key())))
    with TestClient(app, base_url="https://" + host, follow_redirects=False) as target, TestClient(app, base_url="https://auth.kuanguard.com", follow_redirects=False) as central:
        target.headers["origin"] = "https://" + host
        start = post(target, "/auth/portal/start", {"return_path": "/partner"})
        intent = parse_qs(urlsplit(start.json()["login_url"]).query)["intent"][0]
        authorize = central.get("/auth/oidc/start", params={"intent": intent})
        assert authorize.status_code == 303, authorize.text
        params = parse_qs(urlsplit(authorize.headers["location"]).query)
        state = params["state"][0]
        with platform["engine"].begin() as conn:
            pending = one(conn, m.oidc_states, None, m.oidc_states.c.state_hash == digest(state))
        assert params["code_challenge_method"] == ["S256"]
        assert params["code_challenge"] == [base64.urlsafe_b64encode(hashlib.sha256(pending["verifier"].encode()).digest()).decode().rstrip("=")]
        claims = {"iss": metadata["issuer"], "sub": "operator-subject", "aud": "portal-client", "iat": m.now(),
                  "exp": m.now() + timedelta(minutes=5), "nonce": pending["nonce"]}
        if bad_claim == "expired":
            claims["exp"] = m.now() - timedelta(seconds=10)
        elif bad_claim:
            claims[bad_claim] = "tampered"
        token = jwt.encode(claims, signing_key, algorithm="RS256")
        def exchange(url, *, data, timeout):
            assert url == metadata["token_endpoint"]
            assert data["code_verifier"] == pending["verifier"] and data["redirect_uri"] == "https://auth.kuanguard.com/api/auth/oidc/callback"
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"id_token": token})
        monkeypatch.setattr(httpx, "post", exchange)
        assert central.get("/auth/oidc/callback", params={"code": "auth-code", "state": "forged-state"}).status_code == 403
        callback = central.get("/auth/oidc/callback", params={"code": "auth-code", "state": state})
        if bad_claim:
            assert callback.status_code == 403, callback.text
            with platform["engine"].begin() as conn:
                intent_row = one(conn, p.portal_login_intents, None, p.portal_login_intents.c.token_hash == digest(intent))
                assert intent_row["code_hash"] is None
        else:
            assert callback.status_code == 303 and urlsplit(callback.headers["location"]).hostname == host, callback.text
            assert central.get("/auth/oidc/callback", params={"code": "auth-code", "state": state}).status_code == 403
            url = urlsplit(callback.headers["location"])
            assert target.get(url.path.removeprefix("/api") + "?" + url.query).status_code == 303
            assert target.get("/auth/me").json()["partner_id"] == fixed("tenant-partner-a")
    settings.cache_clear()


def test_proxy_signature_cannot_replace_authenticated_host(platform, monkeypatch):
    from kuanguard.api import app
    with platform["engine"].begin() as conn:
        seed_partners(conn)
    host, _ = register_active_test_domain(platform)
    secret = "test-only-BFF-signing-key-do-not-deploy"
    monkeypatch.setenv("PORTAL_PROXY_SECRET", secret)
    settings.cache_clear()
    def headers(timestamp=None, path="/public/portal", asserted=host):
        timestamp = timestamp or str(int(time.time()))
        signed = f"GET\n{path}\n{asserted}\n{timestamp}"
        return {"x-kg-portal-host": asserted, "x-kg-portal-time": timestamp,
                "x-kg-portal-signature": hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()}
    with TestClient(app, base_url="https://api.kuanguard.com") as client:
        good = client.get("/public/portal", headers=headers())
        assert good.status_code == 200 and good.json()["partner"]["slug"] == "megaprotek", good.text
        assert client.get("/public/portal", headers=headers(str(int(time.time()) - 120))).status_code == 403
        assert client.get("/public/portal", headers=headers() | {"x-kg-portal-host": "other.invalid"}).status_code == 403
        assert client.get("/public/portal", headers=headers(path="/auth/me")).status_code == 403
        # Unsigned X-Forwarded-Host never establishes tenant context.
        assert client.get("/public/portal", headers={"x-forwarded-host": host}).json()["partner"] is None
    settings.cache_clear()


def test_erasure_and_archive_include_new_auth_dependencies(platform):
    from backend.tests.test_lifecycle import isolated_erasure
    from kuanguard.lifecycle import canonical, erasure_manifest, execute_erasure, export_archive
    import zipfile
    tenant, user, request, _, _ = isolated_erasure(platform)
    with platform["engine"].begin() as conn:
        create_session(conn, user["id"], tenant, Response(), "testserver")
        intent = add(conn, p.portal_login_intents, tenant_id=tenant, token_hash=digest("private-intent"),
            destination_origin="http://127.0.0.1:3180", return_path="/learn", browser_hash=digest("private-browser"),
            expires_at=m.now() + timedelta(minutes=5))
        state = add(conn, m.oidc_states, state_hash=digest("private-state"), nonce="nonce", verifier="private-verifier",
                    expires_at=m.now() + timedelta(minutes=5))
        add(conn, p.portal_oidc_links, oidc_state_id=state["id"], intent_id=intent["id"])
        archive = platform["tmp"] / "partner-auth-export.zip"
        export_archive(conn, tenant, archive)
        manifest = erasure_manifest(conn, tenant, request["id"])
        assert manifest["auth_sidecars"]["session_contexts"]["rows"] == 1
    with zipfile.ZipFile(archive) as content:
        assert "tables/portal_login_intents.jsonl" not in content.namelist()
        assert all(b"private-verifier" not in content.read(name) for name in content.namelist())
    assert execute_erasure(platform["engine"], manifest, digest(canonical(manifest)))["status"] == "erased"
    with platform["engine"].begin() as conn:
        assert not all_rows(conn, p.portal_oidc_links)
        assert not all_rows(conn, p.session_contexts)
