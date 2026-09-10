from datetime import timedelta
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from kuanguard import models as m
from kuanguard.access import protect_internal_boundary, validate_access_token
from kuanguard.config import Settings


@pytest.mark.parametrize("values", [
    {"product_id": "qidaigo"}, {"resource_product_id": "qidaigo"},
    {"company_apex_domain": "qidaigo.com"},
    {"supabase_project_ref": "one", "expected_supabase_project_ref": "two"},
    {"supabase_project_ref": "eyuctbnlvnbnivwasvqr", "expected_supabase_project_ref": "eyuctbnlvnbnivwasvqr"},
    {"database_url": "postgresql+psycopg://user:unused@db.eyuctbnlvnbnivwasvqr.supabase.co/db"},
    {"database_url": "postgresql+psycopg://user:unused@db.unbound.supabase.co/db"},
    {"app_env": "production", "production_release_approved": True},
])
def test_product_and_production_settings_fail_closed(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_access_boundary_public_alias_cannot_route_internal():
    config = SimpleNamespace(app_env="production", deployment_surface="internal", access_issuer="https://kg.cloudflareaccess.com", access_audience="kg-admin")
    for host in ["api.kuanguard.com", "preview.vercel.app", "127.0.0.1", "qidaigo.com"]:
        with pytest.raises(HTTPException) as error:
            protect_internal_boundary(host, "/internal/portfolio", "forged", config)
        assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        protect_internal_boundary("admin.kuanguard.com", "/internal/imports/preview", "", config)
    assert error.value.status_code == 403
    protect_internal_boundary("api.kuanguard.com", "/webhooks/payments/sandbox", "", config)
    protect_internal_boundary("app.kuanguard.com", "/customer/projects", "", config)


def test_access_jwt_signature_issuer_audience_and_expiry():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    claims = {"iss": "https://kg.cloudflareaccess.com", "aud": "kg-admin", "sub": "authorized-owner", "iat": m.now(), "exp": m.now()+timedelta(minutes=5)}
    encoded = jwt.encode(claims, key, algorithm="RS256")
    assert validate_access_token(encoded, claims["iss"], claims["aud"], key.public_key())["sub"] == "authorized-owner"
    for changed in [{"iss": "https://other.cloudflareaccess.com"}, {"aud": "qidaigo-admin"}, {"exp": m.now()-timedelta(seconds=1)}]:
        token = jwt.encode({**claims, **changed}, key, algorithm="RS256")
        with pytest.raises(HTTPException) as error:
            validate_access_token(token, claims["iss"], claims["aud"], key.public_key())
        assert error.value.status_code == 403
    with pytest.raises(HTTPException):
        validate_access_token(encoded, "http://metadata.google.internal", claims["aud"], key.public_key())
