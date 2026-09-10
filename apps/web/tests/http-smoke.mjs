import assert from "node:assert/strict";
import fs from "node:fs/promises";

const base = process.env.WEB_BASE_URL || "http://127.0.0.1:3180";
const receipt = { checked_at: new Date().toISOString(), base, browser_verified: false, checks: [] };
function record(name) { receipt.checks.push({ name, status: "passed" }); console.log(`PASS ${name}`); }
const publicPages = ["/", "/services", "/services/va", "/services/wva", "/services/shc", "/services/pt", "/services/source-code", "/services/phishing", "/services/training", "/plans/annual-security", "/courses", "/pricing/credits", "/request-quote", "/resources", "/trust", "/about", "/contact", "/legal/privacy", "/legal/terms", "/legal/credits", "/legal/data-processing", "/legal/acceptable-use", "/login"];
for (const path of publicPages) {
  const response = await fetch(`${base}${path}`); assert.equal(response.status, 200, path);
  const html = await response.text(); assert.match(html, /lang="zh-Hant-TW"/); assert.match(html, /KUANGUARD/);
  if (path === "/") for (const label of ["主機弱點檢測", "網站弱點檢測", "系統安全健診", "滲透測試", "源碼安全檢測", "社交工程演練", "線上教育訓練"]) assert.ok(html.includes(label), `missing service ${label}`);
  if (path === "/request-quote") { assert.match(html, /name="email"/); assert.doesNotMatch(html, /type="file"/); }
}
record("23 public SSR routes and seven services; quote form has no assessment upload");
for (const path of ["/dashboard", "/projects", "/findings", "/reports", "/wallet", "/learn", "/admin/overview", "/admin/portfolio"]) {
  const response = await fetch(`${base}${path}`); assert.equal(response.status, 200, path); assert.match(response.headers.get("cache-control") || "", /no-cache|no-store/); assert.match(response.headers.get("x-robots-tag") || "", /noindex/);
}
record("eight private development SSR routes emit revalidation and noindex (production no-store tested separately)");

async function api(path, options = {}, client = {}) {
  const headers = { Origin: base, ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}), ...(client.cookie ? { Cookie: client.cookie } : {}), ...(client.csrf ? { "X-CSRF-Token": client.csrf } : {}), ...(options.method && options.method !== "GET" ? { "Idempotency-Key": options.key || crypto.randomUUID() } : {}), ...options.headers };
  const response = await fetch(`${base}/api${path}`, { method: options.method || "GET", headers, body: options.body === undefined ? undefined : JSON.stringify(options.body) });
  const value = await response.json(); return { response, value };
}
async function login(profile) {
  const result = await api("/auth/dev/login", { method: "POST", body: { profile_key: profile } }); assert.equal(result.response.status, 200);
  const cookie = result.response.headers.getSetCookie().map(s => s.split(";", 1)[0]).join("; "); assert.ok(cookie);
  const client = { cookie, csrf: result.value.csrf_token }; const me = await api("/auth/me", {}, client); assert.equal(me.response.status, 200); client.csrf = me.value.csrf_token; return client;
}
const services = await api("/public/services"); assert.equal(services.response.status, 200); assert.equal(services.value.items.length, 7); record("Next same-origin API rewrite reaches seven-service backend catalog");
const profileResponse = await api("/auth/dev/profiles"); assert.ok(profileResponse.value.items.some(p => p.key === "owner-a")); record("development profiles originate from backend capability endpoint");
const customer = await login("customer-a");
for (const path of ["/customer/dashboard", "/customer/projects", "/customer/wallet", "/customer/campaigns", "/customer/training/courses", "/customer/organization"]) { const { response } = await api(path, {}, customer); assert.equal(response.status, 200, path); }
let result = await api("/internal/imports", {}, customer); assert.equal(result.response.status, 403);
result = await api("/internal/portfolio", {}, customer); assert.equal(result.response.status, 403);
record("customer contract endpoints work; internal imports and portfolio denied");
const learner = await login("learner-a");
for (const path of ["/customer/wallet", "/customer/reports", "/internal/portfolio"]) { const { response } = await api(path, {}, learner); assert.equal(response.status, 403, path); }
result = await api("/learner/enrollments", {}, learner); assert.equal(result.response.status, 200);
record("learner enrollment query works with wallet/report/owner isolation");
const owner = await login("owner-a");
for (const path of ["", "/products", "/finance", "/tasks", "/operations", "/costs", "/integrations"]) { result = await api(`/internal/portfolio${path}`, {}, owner); assert.equal(result.response.status, 200, path); const qidaigo = result.value.items.find(p => p.product === "qidaigo"); assert.ok(qidaigo); assert.notEqual(qidaigo.status, "connected"); assert.equal(result.value.combined_financial_total, null); for (const metric of qidaigo.metrics || []) assert.equal(metric.value, null); }
record("seven owner portfolio sections preserve disconnected QIDAIGO and null totals");
const quote = await api("/public/quote-requests", { method: "POST", body: { company: "Frontend HTTP 驗證（合成）", contact_name: "測試窗口", email: "frontend-contract@example.invalid", services: ["VA", "WVA", "SHC", "PT", "SOURCE", "PHISHING", "TRAINING"], scope: "本機 HTTP 契約驗證，七服務需求，不寄送真實通知。" } }); assert.equal(quote.response.status, 201); assert.ok(quote.value.id); assert.equal(quote.value.email_sent, false);
const leads = await api("/internal/leads", {}, owner); assert.ok(leads.value.items.some(l => l.id === quote.value.id));
record("quote submission is persisted and readable by authorized PM without sending email");
const noCsrf = await api("/customer/tickets", { method: "POST", body: { subject: "Must reject", text: "CSRF contract check" }, headers: { "X-CSRF-Token": "invalid" } }, customer); assert.equal(noCsrf.response.status, 403); record("authenticated mutation rejects invalid CSRF");
await fs.mkdir(new URL("../evidence/", import.meta.url), { recursive: true });
await fs.writeFile(new URL("../evidence/http-smoke.json", import.meta.url), JSON.stringify(receipt, null, 2));
console.log(`HTTP contract smoke complete: ${receipt.checks.length} groups. Browser/viewport interaction not verified.`);
