import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const next = require("next/server");
const env = { KUANGUARD_WEBSITE_ONLY: "true", DEPLOYMENT_SURFACE: "public" };
function load(file) {
  const url = new URL(file, import.meta.url);
  if (url.pathname.endsWith(".json")) return JSON.parse(fs.readFileSync(url, "utf8"));
  const output = ts.transpileModule(fs.readFileSync(url, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  const sandbox = { exports: {}, process: { env }, URL, Headers, Response,
    require: name => name === "next/server" ? next : load(new URL(name + (name.endsWith(".json") ? "" : ".ts"), url).href) };
  vm.runInNewContext(output, sandbox);
  return sandbox.exports;
}
const language = load("../src/lib/locales.ts");
const { proxy } = load("../src/proxy.ts");
const { stallOrder } = load("../src/lib/product-links.ts");
const { translate } = load("../src/lib/translate.ts");
const request = (path, headers = {}) => new next.NextRequest(`https://kuanguard.com${path}`, { headers: { host: "kuanguard.com", ...headers } });

test("browser language weights, scripts, regions and saved preferences select a supported locale", () => {
  for (const [header, saved, expected] of [["zh-HK,zh;q=.9", "", "zh-TW"], ["zh-Hant-CN", "", "zh-TW"], ["zh-SG", "", "zh-CN"], ["ja-JP;q=.5,en-US;q=.9", "", "en"], ["ko-KR,en;q=.8", "", "ko"], ["th-TH", "", "th"], ["vi-VN", "", "vi"], ["ja;q=0,en;q=.5", "", "en"], ["fr,de", "", "zh-TW"], ["ja-JP", "ko", "ko"], ["en", "invalid", "en"], ["ja;q=NaN,en", "", "en"]]) assert.equal(language.preferredLocale(header, saved), expected);
});
test("language selection preserves path and query without changing explicit-language URLs", () => {
  const response = proxy(request("/products?ref=share", { "accept-language": "ja-JP" }));
  assert.equal(response.status, 307);
  assert.equal(response.headers.get("location"), "https://kuanguard.com/ja/products?ref=share");
  assert.match(response.headers.get("cache-control"), /no-store/);
  assert.match(response.headers.get("vary"), /Accept-Language/);
  const explicit = proxy(request("/en/products", { "accept-language": "ja", cookie: "kuanguard-language=ko", "x-website-locale": "vi" }));
  assert.equal(explicit.status, 200);
  assert.equal(explicit.headers.get("content-language"), "en");
  assert.equal(explicit.headers.get("x-middleware-request-x-website-locale"), "en");
  assert.equal(language.localePath("/en/products?ref=share#details", "th"), "/th/products?ref=share#details");
  assert.equal(language.localePath("https://qidaigo.com", "th"), "https://qidaigo.com");
});
test("merchant URLs reach the exact verified service without forwarding unrelated query data", () => {
  for (const prefix of ["", ...language.locales.map(locale => `/${locale}`)]) {
    for (const [path, target] of [["/merchant/apply", stallOrder.apply], ["/login/merchant", stallOrder.login], ["/merchant", stallOrder.login]]) {
      const result = proxy(request(prefix + path + "?token=synthetic-do-not-forward"));
      assert.equal(result.status, 307);
      assert.equal(result.headers.get("location"), target);
    }
  }
  const beauty = proxy(request("/ja/solutions/beauty"));
  assert.equal(beauty.status, 308);
  assert.equal(beauty.headers.get("location"), "https://kuanguard.com/ja/products#beauty");
});
test("locale prefixes and encoded paths cannot expose backend or unpublished workspaces", () => {
  for (const locale of language.locales) for (const path of ["admin", "admin/platform", "api/public/leads", "api/internal/projects", "partner/credits", "dashboard", "%61dmin", "products/unknown", "courses/unknown"]) {
    const result = proxy(request(`/${locale}/${path}`));
    assert.equal(result.status, 404, `${locale}/${path}`);
    assert.match(result.headers.get("cache-control"), /no-store/);
    assert.match(result.headers.get("x-robots-tag"), /noindex/);
  }
});
test("all published translations have all six target values and language alternates", () => {
  const dictionary = load("../src/lib/translations.json");
  assert.ok(Object.keys(dictionary).length >= 488);
  for (const [source, values] of Object.entries(dictionary)) {
    assert.equal(values.length, 6, source);
    assert.ok(values.every(value => typeof value === "string" && value.trim()), source);
  }
  assert.equal(translate(" 商家登入 ", "en"), " Merchant sign-in ");
  assert.equal(translate("NT$1,499", "ja"), "NT$1,499");
  assert.equal(Object.keys(language.languageAlternates("products")).length, 8);
});
