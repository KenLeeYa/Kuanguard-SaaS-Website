import assert from "node:assert/strict";
import fs from "node:fs/promises";
const base = "http://127.0.0.1:3180";
const suffix = new Date().toISOString().replace(/[^0-9]/g, "");
const checks = [];
async function call(path, client, body, method = "POST", status = 200, key = crypto.randomUUID()) {
  const response = await fetch(`${base}/api${path}`, { method: body === undefined ? "GET" : method,
    headers: { Origin: base, ...(client ? { Cookie: client.cookie, "X-CSRF-Token": client.csrf } : {}),
      ...(body !== undefined ? { "Content-Type": "application/json", "Idempotency-Key": key } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body) });
  const value = await response.json();
  assert.equal(response.status, status, `${path}: ${response.status}, code=${value.detail?.code}`);
  return { value, response };
}
async function login(profile) {
  const { response, value } = await call("/auth/dev/login", null, { profile_key: profile });
  return { cookie: response.headers.getSetCookie().map(cookie => cookie.split(";", 1)[0]).join("; "), csrf: value.csrf_token };
}
const customer = await login("customer-a"), owner = await login("owner-a"), other = await login("customer-b");
for (const path of ["/organization/data", "/organization/learners", "/admin/training", "/admin/administration/lifecycle", "/admin/billing/project-costs", "/admin/dispatch"]) {
  const response = await fetch(`${base}${path}`);
  assert.equal(response.status, 200); assert.match(response.headers.get("cache-control") || "", /no-store/);
  assert.match(response.headers.get("x-robots-tag") || "", /noindex/);
}
checks.push("six new private SSR routes preserve no-store and noindex");
const draftPath = "/app/drafts/campaign/new";
const existing = await fetch(`${base}/api${draftPath}`, { headers: { Cookie: customer.cookie } });
if (existing.status === 404) {
  const saved = (await call(draftPath, customer, { expected_version: 0, payload: { name: `合成草稿 ${suffix}` } }, "PUT")).value;
  await call(draftPath, customer, { expected_version: saved.version - 1, payload: { name: "舊視窗不得覆蓋" } }, "PUT", 409);
  const foreign = await fetch(`${base}/api${draftPath}`, { headers: { Cookie: other.cookie } });
  if (foreign.status === 200) assert.notEqual((await foreign.json()).id, saved.id);
  else assert.equal(foreign.status, 404);
  await call(`${draftPath}?version=${saved.version}`, customer, {}, "DELETE");
  checks.push("server draft create, stale-write conflict, actor/tenant scope and versioned cleanup");
} else {
  assert.equal(existing.status, 200);
  checks.push("existing user draft preserved; isolated tests cover writes");
}
const courses = (await call("/internal/training/courses", owner)).value.items;
const learners = (await call("/customer/training/learners", customer)).value.items;
const course = courses[0], learner = learners[0]; assert.ok(course && learner);
const cohort = `http-increment-${suffix}`;
const grant = (await call("/internal/training/entitlements", owner, { course_id: course.id, source: "gift", quantity: 1, cohort,
  starts_at: new Date(Date.now() - 60000).toISOString(), expires_at: new Date(Date.now() + 86400000).toISOString(),
  source_reference: `synthetic-${suffix}`, reason: "本機增量 HTTP 契約驗證，僅合成席次" })).value;
const walletBefore = (await call("/customer/wallet", customer)).value;
const enrollment = (await call("/customer/training/enrollments", customer, { course_id: course.id, learner_id: learner.id, cohort })).value;
assert.equal(enrollment.source, "gift"); assert.equal(enrollment.reservation_id, null);
await call(`/customer/training/enrollments/${enrollment.id}/cancel`, customer, {});
const walletAfter = (await call("/customer/wallet", customer)).value;
assert.equal(walletAfter.available, walletBefore.available); assert.equal(walletAfter.reserved, walletBefore.reserved);
checks.push("dedicated PostgreSQL seat grant/enrollment/cancel does not reserve or debit wallet");
const ticket = (await call("/customer/tickets", customer, { subject: `合成對話 ${suffix}`, text: "本機 HTTP 驗證，不傳送外部通知" })).value;
await call(`/internal/tickets/${ticket.id}/messages`, owner, { text: "內部備註不得出現在客戶頁", visibility: "internal" });
await call(`/internal/tickets/${ticket.id}/messages`, owner, { text: "合成客戶回覆", visibility: "customer" });
const customerTicket = (await call(`/customer/tickets/${ticket.id}`, customer)).value;
assert.equal(customerTicket.messages.length, 1); assert.equal(customerTicket.messages[0].text, "合成客戶回覆");
await call(`/customer/tickets/${ticket.id}`, other, undefined, "GET", 404);
checks.push("ticket reply and internal-note visibility through Next API rewrite");
const projects = (await call("/internal/projects", owner)).value.items;
const project = projects[0]; assert.ok(project);
const task = (await call(`/internal/projects/${project.id}/tasks`, owner, { title: `合成待辦 ${suffix}`, visibility: "internal", internal_note: "本機來源可操作性驗證" })).value;
const customerTasks = await call(`/customer/projects/${project.id}/tasks`, customer);
assert.ok(!customerTasks.value.items.some(row => row.id === task.id));
await call(`/internal/projects/${project.id}/costs`, owner);
await call("/internal/dispatch", owner);
await call("/internal/lifecycle", owner);
await call("/customer/data-export?section=projects", customer);
checks.push("project tasks, private costs, dispatch and lifecycle reads use live authorized endpoints");
await fs.writeFile("docs/evidence/frontend-increment-smoke.json", JSON.stringify({ observed_at: new Date().toISOString(), state: "passed", checks,
  browser_verified: false, real_email: false, real_payment: false, offboarding_executed: false, existing_records_preserved: true,
  synthetic_ids: { seat_grant: grant.id, cancelled_enrollment: enrollment.id, ticket: ticket.id, task: task.id } }, null, 2));
console.log(`PASS ${checks.length} increment groups; no browser, real mail/payment, existing tenant offboard or erasure.`);
