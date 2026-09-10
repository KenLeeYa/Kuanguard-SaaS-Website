"""Authenticate the original Host when a trusted BFF connects through a fixed HTTPS API hostname."""
import hashlib
import hmac
import time

from .config import settings
from .security import fail


def restore_portal_host(request):
    host = request.headers.get("x-kg-portal-host")
    if host is None:
        return  # Direct same-origin ingress already preserves Host.
    timestamp = request.headers.get("x-kg-portal-time", "")
    secret = settings().portal_proxy_secret
    if not secret or not timestamp.isdigit() or len(timestamp) > 13 or abs(time.time() - int(timestamp)) > 60:
        fail(403, "PORTAL_PROXY_INVALID", "代理入口驗證失敗。")
    path = request.scope.get("raw_path", request.url.path.encode()).decode("ascii")
    if request.scope.get("query_string"):
        path += "?" + request.scope["query_string"].decode("ascii")
    signed = f"{request.method}\n{path}\n{host}\n{timestamp}"
    expected = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, request.headers.get("x-kg-portal-signature", "")):
        fail(403, "PORTAL_PROXY_INVALID", "代理入口驗證失敗。")
    from .partner import host_name
    host_name(host)
    request.scope["headers"] = [(name, value) for name, value in request.scope["headers"] if name.lower() != b"host"] + [(b"host", host.encode("ascii"))]
    # Starlette caches parsed headers/URL; replace both after authenticating the transport assertion.
    for attribute in ("_headers", "_url"):
        if hasattr(request, attribute):
            delattr(request, attribute)
