import assert from "node:assert/strict";
import fs from "node:fs/promises";

const base = process.env.WEB_BASE_URL || "http://127.0.0.1:3180";
const checks = [];
const suffix = new Date().toISOString().replace(/[^0-9]/g, "");
function passed(name) { checks.push({ name, status: "passed" }); console.log(`PASS ${name}`); }
async function api(path, client, body, expected = 200, key = crypto.randomUUID()) {
  const response = await fetch(`${base}/api${path}`, { method: body === undefined ? "GET" : "POST", headers: { Origin: base, ...(client?.cookie ? { Cookie: client.cookie, "X-CSRF-Token": client.csrf } : {}), ...(body === undefined ? {} : { "Content-Type": "application/json", "Idempotency-Key": key }) }, body: body === undefined ? undefined : JSON.stringify(body) });
  const value = await response.json();
  assert.equal(response.status, expected, `${path}: ${response.status} ${expected === 200 && response.status !== 200 ? JSON.stringify(value) : ""}`);
  return { value, response };
}
async function login(profile) {
  const { value, response } = await api("/auth/dev/login", null, { profile_key: profile });
  return { cookie: response.headers.getSetCookie().map(cookie => cookie.split(";", 1)[0]).join("; "), csrf: value.csrf_token };
}
const customer = await login("customer-a");
const other = await login("customer-b");
const owner = await login("owner-a");
const finance = await login("finance-a");
const learner = await login("learner-a");

for (const path of ["/learn/courses", "/learn/notifications", "/notifications", "/questionnaires", "/admin/questionnaires", "/admin/tickets", "/admin/changes", "/admin/phishing-operations"]) {
  const response = await fetch(`${base}${path}`);
  assert.equal(response.status, 200, path); assert.match(response.headers.get("x-robots-tag") || "", /noindex/);
}
passed("eight added private SSR routes and OIDC learner alias resolve with noindex");

const workbook = await fs.readFile(new URL("fixtures/recipients.xlsx", import.meta.url));
const { value: group } = await api("/customer/recipient-imports/xlsx", customer, { name: `Frontend Excel ${suffix}`, filename: "recipients.xlsx", content_base64: workbook.toString("base64") });
assert.equal(group.valid_count, 1); assert.equal(group.errors.length, 2); assert.ok(group.id);
passed("XLSX import persists valid recipient and returns duplicate/invalid row errors");

const { value: campaign } = await api("/customer/campaigns", customer, { name: `Frontend unknown ${suffix}`, group_id: group.id, scheduled_at: new Date(Date.now() + 3600000).toISOString() });
await api(`/customer/campaigns/${campaign.id}/schedule`, customer, { confirmed: true });
const { value: dispatched } = await api(`/development/campaigns/${campaign.id}/dispatch`, customer, { outcome: "unknown" });
const message = dispatched.messages[0]; assert.equal(message.status, "unknown");
const { value: unknown } = await api("/internal/phishing/messages?page=1&page_size=20", finance);
assert.equal(unknown.page_size, 20); for (const item of unknown.items) assert.equal(item.tracking_hash, undefined);
const body = { outcome: "rejected", provider_reference: `synthetic-local-${suffix}`, occurred_at: new Date().toISOString(), reason: "本機合成供應商核對紀錄，確認未接受；沒有真實郵件寄送。" };
await api(`/internal/phishing/messages/${message.id}/reconcile`, customer, body, 403);
const reconcileKey = crypto.randomUUID();
const { value: reconciled } = await api(`/internal/phishing/messages/${message.id}/reconcile`, finance, body, 200, reconcileKey);
assert.equal(reconciled.status, "rejected");
await api(`/internal/phishing/messages/${message.id}/reconcile`, finance, body, 200, reconcileKey);
await api(`/internal/phishing/messages/${message.id}/reconcile`, finance, body, 409);
passed("unknown delivery finance reconciliation is authorized, evidenced and idempotent without resending");

const { value: questionnaire } = await api("/customer/questionnaires", customer, { title: `Frontend questionnaire ${suffix}`, supplier: "合成測試供應商", due_at: new Date(Date.now() + 86400000).toISOString(), questions: ["是否記錄帳號權限覆核結果？"] });
const answer = questionnaire.answers[0];
const { value: answered } = await api(`/customer/questionnaires/${questionnaire.id}/answers/${answer.id}`, customer, { answer: "本次為合成測試回覆。", evidence_reference: "合成紀錄 TEST-001，僅保存文字。", expected_revision: answer.revision });
const revision = answered.answers[0].revision; assert.notEqual(revision, answer.revision);
await api(`/customer/questionnaires/${questionnaire.id}`, other, undefined, 404);
await api(`/internal/questionnaires/${questionnaire.id}`, learner, undefined, 403);
const { value: reviewed } = await api(`/internal/questionnaires/${questionnaire.id}/answers/${answer.id}/review`, owner, { decision: "reviewed", reason: "已檢查此合成資料的回覆與文字參考。", expected_revision: revision });
assert.equal(reviewed.answers[0].review_status, "reviewed");
await api(`/customer/questionnaires/${questionnaire.id}/answers/${answer.id}`, customer, { answer: "過時版本不得覆寫", evidence_reference: "TEST-001", expected_revision: revision }, 409);
passed("questionnaire answer/review uses current revision and denies stale or cross-tenant access");

const { value: ticket } = await api("/customer/tickets", customer, { subject: `Frontend support ${suffix}`, text: "合成工單：本機介面契約檢查，不發送真實通知。" });
await api(`/customer/tickets/${ticket.id}`, other, undefined, 404);
const { value: updatedTicket } = await api(`/internal/tickets/${ticket.id}/status`, owner, { status: "in_progress", expected_status: "open", reason: "已由本機測試操作者核對原始合成工單。" });
assert.equal(updatedTicket.status, "in_progress");
await api(`/internal/tickets/${ticket.id}/status`, owner, { status: "closed", expected_status: "open", reason: "過時狀態檢查" }, 409);
const { value: customerTicket } = await api(`/customer/tickets/${ticket.id}`, customer); assert.equal(customerTicket.text, ticket.text); assert.equal(customerTicket.status, "in_progress");
passed("user-owned ticket detail and PM status update preserve original text and reject stale status");

for (const client of [customer, owner, learner]) {
  const { value } = await api("/customer/notifications?page=1&page_size=20", client); assert.equal(value.page_size, 20); assert.ok(Array.isArray(value.items));
  if (value.items.length) { const { value: read } = await api(`/customer/notifications/${value.items[0].id}/read`, client, {}); assert.equal(read.is_read, true); }
}
passed("personal notification pagination works for customer, owner and learner roles");

const { value: customerProjects } = await api("/customer/projects?page_size=100", customer);
const { value: internalProjects } = await api("/internal/projects?page_size=100", owner);
const project = internalProjects.items.find(p => customerProjects.items.some(c => c.id === p.id)); assert.ok(project);
const { value: grant } = await api("/internal/entitlements/grants", owner, { project_id: project.id, service_code: "VA", quantity: 1, reason: "本機前端契約檢查所需的一次合成檢測授權。" });
assert.equal(grant.available, 1);
const { value: batch } = await api(`/internal/projects/${project.id}/batches`, owner, { service_code: "VA", title: `Frontend scope ${suffix}`, planned_assets: ["192.0.2.91"] });
const { value: change } = await api(`/customer/projects/${project.id}/changes`, customer, { batch_id: batch.id, kind: "scope", reason: "合成範圍追加，驗證客戶費用版本確認流程。", proposed_assets: ["192.0.2.92"] });
const { value: offered } = await api(`/internal/changes/${change.id}/offer`, owner, { expected_version: change.version, amount_minor: 10000, reason: "合成追加範圍費用核對，無實際金流扣款。" });
await api(`/customer/changes/${change.id}/confirm`, customer, { version: change.version, intent: "accept" }, 409);
await api(`/customer/changes/${change.id}/confirm`, customer, { version: offered.version, intent: "accept" });
const { value: applied } = await api(`/internal/changes/${change.id}/apply`, owner, { expected_version: offered.version }); assert.equal(applied.status, "applied");
await api(`/internal/batches/${batch.id}/cancel`, owner, { text: "合成本機驗證完成，取消尚未交付批次並釋放原額度預留。" });
const { value: changes } = await api("/internal/changes?page=1&page_size=20", owner); assert.equal(changes.page_size, 20);
passed("finite entitlement, customer-confirmed change version, scope application and release work through Next API proxy");

await fs.mkdir(new URL("../evidence/", import.meta.url), { recursive: true });
await fs.writeFile(new URL("../evidence/operations-smoke.json", import.meta.url), JSON.stringify({ checked_at: new Date().toISOString(), base, browser_verified: false, external_mail_sent: false, real_payment: false, synthetic_records_created: true, checks }, null, 2));
console.log(`Operations HTTP contract checks complete: ${checks.length} groups; this is not browser interaction evidence.`);
