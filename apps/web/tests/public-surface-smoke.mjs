import assert from "node:assert/strict";
import fs from "node:fs/promises";
import http from "node:http";
const base = process.env.PUBLIC_WEB_BASE_URL || "http://127.0.0.1:3181";
const checks = [];
function hostRequest(path, headers = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, base);
    http.get({ hostname: url.hostname, port: url.port, path: url.pathname + url.search, headers }, response => {
      response.resume();
      resolve({ status: response.statusCode, headers: { get: key => response.headers[key.toLowerCase()] } });
    }).on("error", reject);
  });
}
const adminPaths = ["/admin", "/admin/overview", "/admin/portfolio", "/portfolio", "/portfolio/finance", "/imports", "/review", "/overview", "/api/internal/projects", "/api/internal/portfolio", "/internal/projects", "/api/%69nternal/projects", "/%61dmin/portfolio", "/admin/phishing-operations", "/admin/changes", "/admin/questionnaires", "/admin/tickets", "/api/internal/questionnaires", "/api/internal/phishing/messages"];
for (const path of adminPaths) {
  for (const headers of [{}, { Host: "preview-kuanguard.vercel.app" }, { Host: "admin.kuanguard.com" }]) {
    const response = await hostRequest(path, headers); assert.equal(response.status, 404, `${path} ${headers.Host || "origin"}`); assert.match(response.headers.get("cache-control") || "", /no-store/);
  }
  checks.push({ path, status: "blocked_on_all_three_hosts" });
}
const privatePaths = ["/dashboard", "/projects", "/findings", "/reports", "/wallet", "/learn", "/login", "/learn/courses", "/learn/notifications", "/questionnaires", "/notifications"];
for (const path of privatePaths) {
  const response = await fetch(`${base}${path}`); assert.equal(response.status, 200, path); assert.match(response.headers.get("cache-control") || "", /no-store/); assert.match(response.headers.get("x-robots-tag") || "", /noindex/); checks.push({ path, status: "private_no_store_noindex" });
}
const www = await hostRequest("/services/va?reference=smoke", { Host: "www.kuanguard.com" }); assert.equal(www.status, 308); assert.equal(www.headers.get("location"), "https://kuanguard.com/services/va?reference=smoke");
const app = await hostRequest("/", { Host: "app.kuanguard.com" }); assert.equal(app.status, 307); assert.ok(app.headers.get("location").endsWith("/dashboard"));
await fs.mkdir(new URL("../evidence/", import.meta.url), { recursive: true });
await fs.writeFile(new URL("../evidence/public-surface-smoke.json", import.meta.url), JSON.stringify({ checked_at: new Date().toISOString(), base, deployed: false, checks, www_redirect_preserves_path_and_query: true, app_routes_to_dashboard: true }, null, 2));
console.log(`PASS ${checks.length} public-surface groups; ${adminPaths.length * 3} admin/API bypass attempts blocked, ${privatePaths.length} private no-store pages, www/app routing verified locally.`);
