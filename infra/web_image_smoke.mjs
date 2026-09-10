import assert from "node:assert/strict";
import fs from "node:fs";
import crypto from "node:crypto";
import http from "node:http";

assert.equal(process.getuid(), 10001);
assert.equal(process.env.DEPLOYMENT_SURFACE, "internal");
assert.equal(fs.existsSync("/app/.env"), false);
const source = JSON.parse(fs.readFileSync("/app/build-source.json", "utf8"));
assert.equal(source.api, "http://api:8180");
assert.equal(source.surface, "internal");
const manifest = JSON.parse(fs.readFileSync("/app/.next/routes-manifest.json", "utf8"));
const rewrites = Array.isArray(manifest.rewrites) ? manifest.rewrites : Object.values(manifest.rewrites).flat();
assert.ok(rewrites.some(row => row.source === "/api/:path*" && row.destination === "http://api:8180/:path*"));
assert.ok(rewrites.some(row => row.source === "/internal/:path*" && row.destination === "http://api:8180/internal/:path*"));
let ready = false;
for (let attempt = 0; attempt < 30; attempt++) {
  try { ready = (await fetch("http://127.0.0.1:3180/login")).status === 200; } catch {}
  if (ready) break;
  await new Promise(resolve => setTimeout(resolve, 500));
}
assert.ok(ready, "Standalone server must start without host ports or backend connectivity");
const checks = [];
let html = "";
for (const path of ["/login", "/portfolio", "/overview"]) {
  const response = await fetch(`http://127.0.0.1:3180${path}`, { headers: { host: "admin.kuanguard.com" }, redirect: "manual" });
  assert.equal(response.status, 200);
  assert.match(response.headers.get("cache-control"), /private/);
  assert.match(response.headers.get("cache-control"), /no-store/);
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.equal(response.headers.get("x-powered-by"), null);
  html = await response.text();
  assert.ok(html.includes("KUANGUARD"));
  checks.push({ path, status: response.status, cache_control: response.headers.get("cache-control"), body_sha256: crypto.createHash("sha256").update(html).digest("hex") });
}
const staticPath = html.match(/src="(\/_next\/static\/[^" ]+)"/)?.[1];
assert.ok(staticPath);
const staticResponse = await fetch(`http://127.0.0.1:3180${staticPath}`);
assert.equal(staticResponse.status, 200);
// The raw HTTP client preserves the test Host header independently of fetch normalization.
const redirect = await new Promise((resolve, reject) => {
  const request = http.get({ hostname: "127.0.0.1", port: 3180, path: "/plan?check=1", headers: { Host: "www.kuanguard.com" } }, response => {
    response.resume();
    response.on("end", () => resolve({ status: response.statusCode, location: response.headers.location }));
  });
  request.on("error", reject);
});
assert.equal(redirect.status, 308);
assert.equal(redirect.location, "https://kuanguard.com/plan?check=1");
console.log(JSON.stringify({ state: "passed", node: process.version, uid: process.getuid(), surface: process.env.DEPLOYMENT_SURFACE,
  checks, static_asset_status: staticResponse.status, www_redirect_status: redirect.status, redirect_path_query_preserved: true,
  compiled_api_origin: source.api, source_manifest: source.files, backend_authenticated_flow: "not_tested_network_none", public_ports: [] }));
