"""Cloudflare Access validation supplements, never replaces, application sessions and roles."""
from urllib.parse import urlparse

import jwt

from .config import settings
from .security import fail


def validate_access_token(token, issuer, audience, signing_key=None):
    parsed = urlparse(issuer)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".cloudflareaccess.com") or not audience:
        fail(503, "ACCESS_NOT_CONFIGURED", "內部入口尚未設定有效的 Access 驗證。")
    if not token:
        fail(403, "ACCESS_REQUIRED", "需要員工入口驗證。")
    try:
        key = signing_key or jwt.PyJWKClient(issuer.rstrip("/")+"/cdn-cgi/access/certs", timeout=5).get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=["RS256"], issuer=issuer.rstrip("/"), audience=audience,
                          options={"require": ["exp", "iat", "iss", "aud", "sub"]})
    except jwt.PyJWTError:
        fail(403, "ACCESS_INVALID", "員工入口驗證無效或已過期。")


def protect_internal_boundary(host, path, token, config=None):
    config = config or settings()
    if not path.startswith(("/internal", "/platform")):
        return
    if config.app_env in {"development", "test"} and config.deployment_surface == "local":
        return
    if host.lower().split(":")[0] != "admin.kuanguard.com":
        fail(404, "INTERNAL_NOT_ROUTED", "此入口沒有內部管理路由。")
    validate_access_token(token, config.access_issuer, config.access_audience)
