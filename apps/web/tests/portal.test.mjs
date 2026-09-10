import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import crypto from "node:crypto";
import ts from "typescript";

function load(path, env, dependencies = {}, fetcher = fetch) {
  const source = fs.readFileSync(new URL(path, import.meta.url), "utf8");
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const sandbox = { exports: {}, process: { env }, URL, Headers, Response, AbortSignal, fetch: fetcher,
    require: name => name === "node:crypto" ? crypto : dependencies[name] };
  vm.runInNewContext(js, sandbox);
  return sandbox.exports;
}
const helper = env => load("../src/lib/server-api.ts", env);
const key = "synthetic-bff-test-key";

test("unconfigured or misbound BFF cannot silently lose its authenticated host", () => {
  assert.throws(() => helper({}).portalHeaders("portal.example.test", "GET", "/public/portal"), /signing key/);
  for (const url of ["https://qidaigo.com", "https://app.qidaigo.com", "https://api.example.test/private", "https://user:pass@api.example.test", "file:///", "ftp://api.example.test"]) {
    assert.throws(() => helper({ API_INTERNAL_URL: url }).apiOrigin(), /Invalid API binding/);
  }
  assert.throws(() => helper({ VERCEL: "1", API_INTERNAL_URL: "http://api.kuanguard.com", PORTAL_PROXY_SECRET: key }).apiOrigin(), /Verified HTTPS/);
  assert.equal(helper({ VERCEL: "1", API_INTERNAL_URL: "https://api.kuanguard.com", PORTAL_PROXY_SECRET: key }).apiOrigin().host, "api.kuanguard.com");
});

function request(path, extra = {}) {
  const req = new Request("http://127.0.0.1:3180/api/" + path, { headers: { host: "portal.partner.example", ...extra } });
  req.nextUrl = new URL(req.url);
  return req;
}
function route(env, fetcher, surface = "public") {
  return load("../src/app/api/[...path]/route.ts", env, {
    "@/lib/server-api": helper(env), "@/lib/surface": { deploymentSurface: () => surface },
  }, fetcher);
}
test("BFF signs actual Host and exact upstream path/query, discards forged forwarding headers", async () => {
  let captured;
  const api = route({ API_INTERNAL_URL: "http://api:8180", PORTAL_PROXY_SECRET: key }, async (url, init) => {
    captured = { url, init };
    return Response.json({ ok: true }, { headers: { "set-cookie": "kg_session=synthetic; HttpOnly; Path=/; SameSite=Lax" } });
  });
  const res = await api.GET(request("public/portal?slug=hello%20world", { "x-forwarded-host": "evil.example", "x-kg-portal-host": "evil.example", cookie: "kg_session=synthetic" }), { params: Promise.resolve({ path: ["public", "portal"] }) });
  assert.equal(res.status, 200);
  assert.equal(captured.url.href, "http://api:8180/public/portal?slug=hello%20world");
  const headers = captured.init.headers;
  assert.equal(headers.get("x-kg-portal-host"), "portal.partner.example");
  assert.equal(headers.get("x-forwarded-host"), null);
  assert.equal(headers.get("x-kg-portal-signature"), crypto.createHmac("sha256", key).update(`GET\n/public/portal?slug=hello%20world\nportal.partner.example\n${headers.get("x-kg-portal-time")}`).digest("hex"));
  assert.match(res.headers.get("cache-control"), /no-store/);
  assert.match(res.headers.get("set-cookie"), /HttpOnly/);
});
test("public surface denies admin routes and missing signing configuration before any network call", async () => {
  let called = false;
  const api = route({}, async () => { called = true; throw new Error("must not fetch"); });
  for (const path of [["platform", "overview"], ["internal", "projects"]]) {
    assert.equal((await api.GET(request(path.join("/")), { params: Promise.resolve({ path }) })).status, 404);
  }
  assert.equal((await api.GET(request("public/portal"), { params: Promise.resolve({ path: ["public", "portal"] }) })).status, 503);
  assert.equal(called, false);
});

test("unknown product URLs return a real 404 before streaming, while product entries reach the page", () => {
  class NextResponse extends Response {
    static next() { return new Response(null, { status: 200 }); }
  }
  const routes = load("../src/lib/commerce.ts", {});
  const policy = load("../src/proxy.ts", {}, {
    "next/server": { NextResponse }, "./lib/surface": { deploymentSurface: () => "public" }, "./lib/commerce": routes,
    "./lib/website": { websiteOnly: () => false },
  });
  for (const [path, expected] of [["/products", 200], ["/products/ordering", 200], ["/products/unknown", 404], ["/products/ordering/unknown", 404]]) {
    const response = policy.proxy({ nextUrl: { clone: () => new URL("https://kuanguard.com" + path) }, headers: new Headers({ host: "kuanguard.com" }) });
    assert.equal(response.status, expected, path);
    if (expected === 404) assert.match(response.headers.get("x-robots-tag"), /noindex/);
  }
});

test("website release blocks all backend forwarding even with otherwise valid credentials", async () => {
  let calls = 0;
  const api = route({ KUANGUARD_WEBSITE_ONLY: "true", API_INTERNAL_URL: "https://api.kuanguard.com", PORTAL_PROXY_SECRET: key }, async () => { calls++; return Response.json({ ok: true }); });
  for (const path of ["auth/dev-login", "public/leads", "partner/credits", "internal/projects", "platform/overview"]) {
    const response = await api.POST(request(path), { params: Promise.resolve({ path: path.split("/") }) });
    assert.equal(response.status, 404, path);
    assert.match(response.headers.get("cache-control"), /no-store/);
  }
  assert.equal(calls, 0);
});

test("website release allows only public pages and keeps Vercel hostnames on the corporate home", () => {
  class NextResponse extends Response { static next() { return new Response(null, { status: 200 }); } }
  const commerce = load("../src/lib/commerce.ts", {});
  const catalog = load("../src/lib/catalog.ts", {});
  const env = { KUANGUARD_WEBSITE_ONLY: "true" };
  const website = load("../src/lib/website.ts", env, { "./commerce": commerce, "./catalog": catalog });
  const policy = load("../src/proxy.ts", env, {
    "next/server": { NextResponse }, "./lib/surface": { deploymentSurface: () => "public" }, "./lib/commerce": commerce, "./lib/website": website,
  });
  for (const [path, status] of [["/", 200], ["/contact", 200], ["/services/va", 200], ["/login", 200], ["/partner/login", 200], ["/admin", 404], ["/partner/credits", 404], ["/dashboard", 404], ["/api/auth/dev-login", 404], ["/api/public/leads", 404], ["/internal/projects", 404], ["/not-a-page", 404]]) {
    for (const host of ["kuanguard.com", "kuanguard-website.vercel.app"]) {
      assert.equal(policy.proxy({ nextUrl: { clone: () => new URL(`https://${host}${path}`) }, headers: new Headers({ host }) }).status, status, `${host}${path}`);
    }
  }
});
