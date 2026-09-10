import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

function surface(env) {
  const source = fs.readFileSync(new URL("../src/lib/surface.ts", import.meta.url), "utf8");
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const sandbox = { exports: {}, process: { env } };
  vm.runInNewContext(js, sandbox);
  return sandbox.exports.deploymentSurface();
}

test("production defaults to public, local development is explicit and portable", () => {
  assert.equal(surface({ NODE_ENV: "production" }), "public");
  assert.equal(surface({ NODE_ENV: "development" }), "local");
  assert.equal(surface({ NODE_ENV: "production", DEPLOYMENT_SURFACE: "internal" }), "internal");
});
test("Vercel cannot expose internal or local admin surfaces through any alias", () => {
  assert.equal(surface({ VERCEL: "1" }), "public");
  assert.equal(surface({ VERCEL: "1", DEPLOYMENT_SURFACE: "public" }), "public");
  assert.throws(() => surface({ VERCEL: "1", DEPLOYMENT_SURFACE: "internal" }), /only expose/);
  assert.throws(() => surface({ VERCEL: "1", DEPLOYMENT_SURFACE: "local" }), /only expose/);
});
test("invalid deployment surface fails closed", () => {
  assert.throws(() => surface({ DEPLOYMENT_SURFACE: "preview-admin" }), /must be/);
});

function luminance(hex) {
  return hex.match(/[\da-f]{2}/gi).map(n => parseInt(n, 16) / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((sum, value, i) => sum + value * [.2126, .7152, .0722][i], 0);
}
function contrast(a, b) { const x = luminance(a), y = luminance(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); }
test("primary body and actionable text token pairs meet AA normal text contrast", () => {
  for (const [name, foreground, background] of [["body", "172B4D", "FFFFFF"], ["muted", "52657B", "FFFFFF"], ["action", "FFFFFF", "0F766E"], ["hero", "B3C4D2", "0B1F33"], ["hero accent", "7DDDC1", "0B1F33"], ["error", "9A2E3E", "FFF2F4"]]) {
    assert.ok(contrast(foreground, background) >= 4.5, `${name} contrast below 4.5:1`);
  }
});
