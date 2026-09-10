"""Opt-in loopback HTTP acceptance; only synthetic login/session writes, no business mutations."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:3180"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("Pass --run to create and revoke synthetic local sessions")
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        raise SystemExit("Use a new receipt path within this workspace")
    checks = []

    def check(name, actual, expected):
        assert actual == expected, f"{name}: {actual!r} != {expected!r}"
        checks.append({"check": name, "result": actual})

    def post(client, path, payload=None):
        headers = {"origin": BASE, "idempotency-key": str(uuid4())}
        current = client.get("/api/auth/me")
        if current.status_code == 200:
            headers["x-csrf-token"] = current.json()["csrf_token"]
        return client.post("/api" + path, json=payload or {}, headers=headers)

    with httpx.Client(base_url=BASE, timeout=30, follow_redirects=False) as client:
        health = client.get("/api/health").json()
        check("local development product", (health["product"], health["environment"]), ("kuanguard", "development"))
        paths = ["/", "/features", "/pricing", "/partners", "/about", "/contact", "/merchant/apply", "/privacy", "/terms", "/terms/merchants", "/terms/partners", "/security"]
        paths += ["/solutions/" + industry for industry in ["restaurant", "beverage", "food-stall", "retail", "beauty"]]
        for path in paths:
            response = client.get(path)
            check("page " + path, response.status_code, 200)
            canonical = re.search(r'<link rel="canonical" href="([^"]+)"', response.text)
            check("canonical " + path, canonical[1].rstrip("/") if canonical else None, ("https://kuanguard.com" + path).rstrip("/"))
            check("safe content " + path, response.headers.get("x-content-type-options"), "nosniff")
        home = client.get("/").text
        check("merchant home positioning", "點餐" in home and "application/ld+json" in home, True)
        static = re.search(r'src="(/_next/static/[^" ]+)"', home)
        check("built static asset", client.get(static[1]).status_code if static else None, 200)
        for path in ["/login", "/partner/login", "/partner", "/admin/platform", "/merchant"]:
            response = client.get(path)
            check("private entry " + path, response.status_code, 200)
            check("no cache " + path, "no-store" in response.headers.get("cache-control", ""), True)
        check("robots", client.get("/robots.txt").status_code, 200)
        check("sitemap", client.get("/sitemap.xml").status_code, 200)
        product = client.get("/api/public/commerce").json()
        check("billing projection disabled", product["pricing"]["charge_enabled"], False)
        check("existing merchant bridge", urlsplit(product["entry_url"]).hostname in {"app.qidaigo.com", "app.kuanguard.com"}, True)
        for host in ["portal.megaprotek.com.tw", "not-a-partner.example"]:
            response = client.get("/api/public/portal", headers={"host": host, "x-forwarded-host": "127.0.0.1:3180"})
            check("unsigned forwarding cannot activate " + host, response.status_code, 404)
        branded = client.get("/api/public/portal?slug=megaprotek")
        check("signed query transport", branded.status_code, 200)
        check("configured partner slug", branded.json()["partner"]["slug"], "megaprotek")
        login = post(client, "/auth/dev/login", {"profile_key": "partner-admin-a"})
        check("partner login", login.status_code, 200)
        check("host-only session", "domain=" not in login.headers.get("set-cookie", "").lower(), True)
        check("HttpOnly session", "httponly" in login.headers.get("set-cookie", "").lower(), True)
        customer = client.get("/api/partner/customers").json()["items"][0]["customer_tenant_id"]
        other = "00000000-0000-0000-0000-000000000000"
        check("foreign customer denied", post(client, f"/partner/customers/{other}/enter").status_code, 403)
        check("personal delegation", post(client, f"/partner/customers/{customer}/enter").status_code, 200)
        check("delegation session", client.get("/api/auth/me").json()["delegated"], True)
        check("reused scoped projects", client.get("/api/partner/workspace/internal/projects").status_code, 200)
        check("return partner", post(client, "/partner/return").status_code, 200)
        check("delegation revoked on return", client.get("/api/auth/me").json()["delegated"], False)
        post(client, "/auth/logout")
        start = post(client, "/auth/portal/start", {"partner_slug": "megaprotek", "return_path": "/partner"})
        check("central login start", start.status_code, 200)
        intent = parse_qs(urlsplit(start.json()["login_url"]).query)["intent"][0]
        completed = post(client, "/auth/portal/dev-complete", {"intent": intent, "profile_key": "partner-admin-a"})
        check("synthetic central identity", completed.status_code, 200)
        callback = completed.json()["redirect"]
        check("callback exact destination", callback.startswith(BASE + "/api/auth/portal/callback?"), True)
        with httpx.Client(timeout=30) as other_browser:
            check("code without browser binding denied", other_browser.get(callback).status_code, 403)
        redeemed = client.get(callback)
        check("host-bound exchange", redeemed.status_code, 303)
        check("safe post-login path", redeemed.headers.get("location"), "/partner")
        check("exchange replay denied", client.get(callback).status_code, 403)
        check("restored partner role", "partner_admin" in client.get("/api/auth/me").json()["roles"], True)
        check("session logout", post(client, "/auth/logout").status_code, 200)
        check("revoked session denied", client.get("/api/auth/me").status_code, 401)
    receipt = {"state": "passed", "observed_at": datetime.now(timezone.utc).isoformat(), "base": BASE,
               "scope": "actual_node_bff_python_postgres_http_synthetic_sessions", "checks": checks,
               "home_sha256": hashlib.sha256(home.encode()).hexdigest(), "business_data_mutations": 0,
               "external_providers_called": 0, "visual_browser_qa": "not_performed_administrator_policy",
               "credentials_tokens_personal_rows_logged": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"state": "passed", "checks": len(checks), "receipt": output.relative_to(ROOT).as_posix()}))


if __name__ == "__main__":
    main()
