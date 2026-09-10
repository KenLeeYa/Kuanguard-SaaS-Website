import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import http from "node:http";

const base = process.argv[2] || "http://127.0.0.1:3181";
const evidencePath = process.argv[3];
const local = new URL(base).hostname === "127.0.0.1";
const checks = [];
async function get(path, init = {}) {
  if (local) return new Promise((resolve, reject) => {
    const url = new URL(path, base);
    const request = http.request(url, { method: init.method || "GET", headers: { host: "kuanguard.com", ...init.headers } }, response => {
      const chunks = [];
      response.on("data", chunk => chunks.push(chunk));
      response.on("end", () => resolve(new Response(Buffer.concat(chunks), { status: response.statusCode, headers: response.headers })));
      response.on("error", reject);
    });
    request.setTimeout(15000, () => request.destroy(new Error(`Request timed out: ${path}`)));
    request.on("error", reject);
    request.end();
  });
  return fetch(new URL(path, base), { redirect: "manual", signal: AbortSignal.timeout(15000), ...init,
    headers: init.headers });
}
async function page(path) {
  const response = await get(path);
  assert.equal(response.status, 200, path);
  assert.equal(response.headers.get("x-content-type-options"), "nosniff", path);
  const html = await response.text();
  assert.match(html, /<h1[ >]/, path);
  checks.push({ path, status: response.status });
  return html;
}
const home = await page("/");
assert.match(home, /數位科技/);
assert.match(home, /走進每一天的營運/);
if (local || new URL(base).hostname === "kuanguard.com") {
  const canonical = home.match(/<link rel="canonical" href="([^"]+)"/);
  assert.ok(canonical, "home canonical link");
  assert.equal(new URL(canonical[1]).href, "https://kuanguard.com/");
} else assert.ok(/noindex/.test(home), "deployment alias should not be indexed");
const sitemap = await get("/sitemap.xml");
assert.equal(sitemap.status, 200);
const routes = [...(await sitemap.text()).matchAll(/<loc>([^<]+)<\/loc>/g)].map(match => new URL(match[1]).pathname).filter(path => path !== "/");
for (let index = 0; index < routes.length; index += 4) await Promise.all(routes.slice(index, index + 4).map(page));
const contact = await page("/contact");
assert.match(contact, /mailto:ada76145@gmail.com/);
assert.match(contact, /開啟郵件程式/);
assert.match(contact, /本站不會儲存表單內容/);
const pricing = await page("/pricing");
assert.match(pricing, /merchant-website-20260910-v1/);
assert.doesNotMatch(pricing, /目前無法取得價目|待取得方案/);
for (const path of ["/login", "/partner/login", "/merchant"]) assert.match(await page(path), /平台入口準備中/);
for (const path of ["/admin", "/admin/platform", "/dashboard", "/partner/credits", "/internal/projects", "/products/unknown", "/courses/unknown"]) {
  const response = await get(path);
  assert.equal(response.status, 404, path);
  assert.match(response.headers.get("cache-control"), /no-store/, path);
  checks.push({ path, status: response.status });
}
for (const path of ["/api/auth/dev-login", "/api/public/leads", "/api/partner/credits", "/api/platform/overview"]) {
  const response = await get(path, { method: "POST" });
  assert.equal(response.status, 404, path);
  checks.push({ path, method: "POST", status: response.status });
}
const assets = [...new Set([...home.matchAll(/(?:src|href)="([^" ]*\/_next\/static\/[^" ]+)"/g)].map(match => match[1].replaceAll("&amp;", "&")))];
assert.ok(assets.length > 0);
for (const path of assets) {
  const response = await get(path);
  assert.equal(response.status, 200, path);
  assert.match(response.headers.get("content-type"), /javascript|css/, path);
  checks.push({ path, status: response.status });
}
if (local) {
  const response = await get("/products/ordering?utm_source=release", { headers: { host: "www.kuanguard.com" } });
  assert.equal(response.status, 308);
  assert.equal(response.headers.get("location"), "https://kuanguard.com/products/ordering?utm_source=release");
  checks.push({ path: "www redirect preserves path/query", status: response.status });
}
const result = { state: "passed", observed_at: new Date().toISOString(), base_url: base, public_routes: routes.length + 1, checks, browser_qa: "not_performed_browser_runtime_unavailable", mail_sent: false, database_mutations: 0 };
if (evidencePath) await writeFile(evidencePath, JSON.stringify(result, null, 2) + "\n");
console.log(JSON.stringify({ state: result.state, base_url: base, public_routes: result.public_routes, checks: checks.length }));
