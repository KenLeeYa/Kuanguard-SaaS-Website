import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { randomUUID } from "node:crypto";
import ts from "typescript";

const source = fs.readFileSync(new URL("../src/lib/draft-store.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const sandbox = { exports: {}, crypto: { randomUUID }, Error, Promise };
vm.runInNewContext(compiled, sandbox);
const { DraftStore } = sandbox.exports;
const failure = status => Object.assign(new Error(`HTTP ${status}`), { status });
const record = (version, payload) => ({ id: "fixture", version, payload, updated_at: "2026-09-10T00:00:00Z", expires_at: "2026-09-11T00:00:00Z" });
function service(initial = null) {
  let current = initial;
  const writes = [], deletes = [];
  return { writes, deletes, get current() { return current; }, set current(value) { current = value; }, transport: {
    get: async () => { if (!current) throw failure(404); return current; },
    put: async (version, payload, key) => { writes.push({ version, payload, key }); if (version !== (current?.version || 0)) throw failure(409); return current = record(version + 1, payload); },
    remove: async (version, key) => { deletes.push({ version, key }); if (current && version !== current.version) throw failure(409); current = null; },
  } };
}

test("draft restores actor-provided server data and creates only after changes", async () => {
  const api = service(); const draft = new DraftStore({ name: "" }, api.transport);
  await draft.load(); assert.equal(draft.dirty, false); assert.equal(await draft.save(), true); assert.equal(api.writes.length, 0);
  draft.edit({ name: "event" }); assert.equal(draft.dirty, true); await draft.save(); assert.equal(api.writes[0].version, 0); assert.equal(draft.dirty, false);
  const restored = new DraftStore({ name: "" }, api.transport); await restored.load(); assert.equal(restored.getSnapshot().payload.name, "event"); assert.equal(restored.getSnapshot().restored, true);
});

test("in-flight saves preserve later typing and serialize the next expected version", async () => {
  const api = service(); let release;
  const firstPut = api.transport.put;
  api.transport.put = async (...args) => { if (!api.writes.length) await new Promise(resolve => { release = resolve; }); return firstPut(...args); };
  const draft = new DraftStore({ name: "" }, api.transport); await draft.load(); draft.edit({ name: "first" });
  const first = draft.save(); await Promise.resolve(); draft.edit({ name: "latest" }); const second = draft.save(); release();
  await first; await second; assert.equal(api.current.payload.name, "latest"); assert.equal(api.writes.length, 2); assert.equal(api.writes[1].version, 1); assert.equal(draft.dirty, false);
});

test("conflict retains local input, reads remote and forbids automatic overwrite", async () => {
  const api = service(record(1, { name: "baseline" })); const draft = new DraftStore({ name: "" }, api.transport); await draft.load();
  draft.edit({ name: "local input" }); api.current = record(2, { name: "other window" });
  assert.equal(await draft.save(), false); assert.equal(draft.getSnapshot().conflict, true); assert.equal(draft.getSnapshot().payload.name, "local input"); assert.equal(draft.getSnapshot().remote.payload.name, "other window");
  assert.equal(await draft.save(), false); assert.equal(api.writes.length, 1); assert.equal(api.current.payload.name, "other window");
  await draft.load(); assert.equal(draft.getSnapshot().payload.name, "other window"); assert.equal(draft.getSnapshot().conflict, false);
});

test("lost response retries keep the same key and accept unchanged server content", async () => {
  const api = service(); const originalPut = api.transport.put; let lost = true;
  api.transport.put = async (version, payload, key) => {
    if (!lost && api.current?.version === version + 1 && api.current.payload.name === payload.name) { api.writes.push({ version, payload, key }); return api.current; }
    const result = await originalPut(version, payload, key); if (lost) { lost = false; throw new Error("response lost"); } return result;
  };
  const draft = new DraftStore({ name: "" }, api.transport); await draft.load(); draft.edit({ name: "saved remotely" });
  assert.equal(await draft.save(), false); assert.equal(draft.dirty, true); assert.equal(await draft.save(), true);
  assert.equal(api.writes[0].key, api.writes[1].key); assert.equal(api.current.version, 1); assert.equal(draft.dirty, false);
});

test("clear checks the loaded version and retains another window's newer draft", async () => {
  const api = service(record(1, { name: "baseline" })); const draft = new DraftStore({ name: "" }, api.transport); await draft.load();
  api.current = record(2, { name: "newer draft" }); assert.equal(await draft.clear(), false);
  assert.equal(api.deletes[0].version, 1); assert.equal(api.current.payload.name, "newer draft"); assert.equal(draft.getSnapshot().conflict, true);
  await draft.load(); assert.equal(await draft.clear(), true); assert.equal(api.deletes[1].version, 2); assert.equal(draft.getSnapshot().payload.name, "");
  draft.edit({ name: "next draft" }); assert.equal(await draft.save(), true); assert.equal(api.current.payload.name, "next draft");
});

test("clearing an empty draft does not leave the write queue stuck", async () => {
  const api = service(); const draft = new DraftStore({ name: "" }, api.transport); await draft.load();
  assert.equal(await draft.clear(), true); assert.equal(api.deletes.length, 0); draft.edit({ name: "after clear" }); assert.equal(await draft.save(), true);
});
