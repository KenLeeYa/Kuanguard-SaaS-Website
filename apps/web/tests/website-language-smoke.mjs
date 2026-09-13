import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import http from "node:http";

const base = process.argv[2] || "http://127.0.0.1:3182";
const evidencePath = process.argv[3];
const isLocal = new URL(base).hostname === "127.0.0.1";
const locales = ["zh-TW", "zh-CN", "en", "ja", "ko", "th", "vi"];
const form = "https://docs.google.com/forms/d/e/1FAIpQLSf859kVKh77cjNjpS26HWNqFdN851UdOQ6htlJUc9pgBlBBLw/viewform";
const checks = [];
async function get(path, headers = {}, method = "GET") {
  if (!isLocal) return fetch(new URL(path, base), { redirect: "manual", headers, method, signal: AbortSignal.timeout(30000) });
  return new Promise((resolve, reject) => {
    const req = http.request(new URL(path, base), { method, headers: { host: "kuanguard.com", ...headers } }, response => {
      const chunks = [];
      response.on("data", chunk => chunks.push(chunk));
      response.on("end", () => resolve(new Response(Buffer.concat(chunks), { status: response.statusCode, headers: response.headers })));
      response.on("error", reject);
    });
    req.setTimeout(30000, () => req.destroy(new Error(`Timeout: ${path}`)));
    req.on("error", reject); req.end();
  });
}
const presentation = html => html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, "").replace(/<style\b[^>]*>[\s\S]*?<\/style>/g, "");
const visible = html => presentation(html).replace(/<select\b[^>]*>[\s\S]*?<\/select>/g, "").replace(/<[^>]*>/g, " ");
for (const [header, target] of [["zh-HK", "zh-TW"], ["zh-CN", "zh-CN"], ["en-US", "en"], ["ja-JP", "ja"], ["ko-KR", "ko"], ["th-TH", "th"], ["vi-VN", "vi"]]) {
  const response = await get("/products?source=language-smoke", { "accept-language": header });
  assert.equal(response.status, 307);
  assert.equal(new URL(response.headers.get("location"), base).pathname, `/${target}/products`);
  assert.equal(new URL(response.headers.get("location"), base).search, "?source=language-smoke");
  assert.match(response.headers.get("cache-control"), /no-store/);
  checks.push({ check: "browser language", header, target, status: response.status });
}
const saved = await get("/products", { "accept-language": "ja", cookie: "kuanguard-language=vi" });
assert.equal(new URL(saved.headers.get("location"), base).pathname, "/vi/products");
const sitemapResponse = await get("/sitemap.xml");
assert.equal(sitemapResponse.status, 200);
const sitemap = await sitemapResponse.text();
const routes = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map(match => new URL(match[1]).pathname);
assert.equal(routes.length, 238);
assert.equal(new Set(routes).size, routes.length);
assert.ok(!routes.some(route => /beauty|merchant\/apply|\/login|\/courses/.test(route)));
async function page(path) {
  const locale = path.split("/")[1];
  const response = await get(path, { "accept-language": "ko", cookie: "kuanguard-language=vi" });
  assert.equal(response.status, 200, path);
  assert.equal(response.headers.get("content-language"), locale, path);
  assert.equal(response.headers.get("x-content-type-options"), "nosniff", path);
  const html = presentation(await response.text());
  assert.match(html, new RegExp(`<html[^>]*lang="${locale}"`), path);
  assert.equal([...html.matchAll(/<h1(?:\s|>)/g)].length, 1, `single h1 ${path}`);
  assert.match(html, /<main id="main-content"/, path);
  assert.match(html, /<meta name="description" content="[^\"]+"/, path);
  assert.ok(html.includes(`<link rel="canonical" href="https://kuanguard.com${path}"`), `canonical ${path}`);
  for (const value of [...locales, "x-default"]) assert.ok(html.includes(`hrefLang="${value}"`) || html.includes(`hreflang="${value}"`), `alternate ${value} ${path}`);
  if (["en", "ko", "th", "vi"].includes(locale)) {
    const untranslated = visible(html).match(/[\u3400-\u9fff][^<>]{0,100}/g) || [];
    assert.equal(untranslated.length, 0, `untranslated content ${path}: ${untranslated.slice(0, 3).join("; ")}`);
  }
  for (const [, href] of html.matchAll(/<a\b[^>]*href="([^\"]+)"/g)) if (href.startsWith("/") && !href.startsWith("//")) {
    const pathname = new URL(href, base).pathname;
    assert.ok(pathname === `/${locale}` || pathname.startsWith(`/${locale}/`), `locale-preserving link ${path}: ${href}`);
  }
  const route = path.split("/").slice(2).join("/");
  if (["", "products"].includes(route)) {
    assert.equal([...html.matchAll(/class="kg-product-card"/g)].length, 3, `three own products ${path}`);
    for (const id of ["ordering", "beauty", "studymesh"]) assert.ok(html.includes(`id="${id}"`), `product anchor ${path}`);
    assert.ok(html.includes('href="https://getstudymesh.com"'), path);
    assert.ok(!html.includes('href="https://getstudymesh.com/login"'), "StudyMesh sign-in is not active");
  }
  if (["", "solutions"].includes(route)) {
    const domains = html.match(/<div class="kg-domain-grid">([\s\S]*?)<\/div>/)?.[1] || "";
    assert.equal([...domains.matchAll(/<article\b/g)].length, 8, `eight cooperation areas ${path}`);
  }
  if (["", "partners"].includes(route)) {
    assert.equal([...html.matchAll(/<details>/g)].length, 6, `six cooperation FAQ items ${path}`);
    assert.ok(html.includes(`href="/${locale}/contact?kind=partner"`), path);
    const vision = html.match(/<section[^>]*id="vision"[\s\S]*?<\/section>/)?.[0] || "";
    assert.ok(vision.includes("kg-platform-status"), `planning status ${path}`);
    assert.doesNotMatch(vision, /<(input|form|button|select)\b/, `static vision ${path}`);
    assert.doesNotMatch(html, /href="#"|<input\b|<form\b/, `no pretend portal ${path}`);
  }
  if (route === "partners") assert.ok(html.includes(`href="/${locale}/partner/login"`), "preserve partner login destination");
  if (["", "products", "solutions", "partners", "about", "contact"].includes(route)) {
    assert.ok(html.includes(`href="/${locale}/services"`), "preserve enterprise security");
    for (const [, href] of html.matchAll(/<a\b[^>]*href="([^\"]*#[^\"]+)"/g)) {
      const target = new URL(href.replaceAll("&amp;", "&"), base);
      if (target.origin === new URL(base).origin && target.pathname.replace(/\/$/, "") === path) assert.ok(html.includes(`id="${target.hash.slice(1)}"`), `working anchor ${path}: ${href}`);
    }
  }
  if (path.endsWith("/products/ordering")) {
    assert.ok(html.includes('href="https://qidaigo.com"'), path);
    assert.ok(html.includes('href="https://app.qidaigo.com/login"'), path);
    assert.ok(html.includes(`href="${form}"`), path);
    assert.doesNotMatch(visible(html), /美業|美业|Beauty studio|美容サロン|뷰티 스튜디오/, path);
  }
  checks.push({ check: "page", path, status: response.status });
  return html;
}
for (let i = 0; i < routes.length; i += 4) await Promise.all(routes.slice(i, i + 4).map(page));
for (const locale of locales) {
  for (const [alias, canonical] of [["legal/privacy", "privacy"], ["legal/terms", "terms"], ["trust", "security"]]) {
    const response = await get(`/${locale}/${alias}`);
    assert.equal(response.status, 308);
    assert.equal(new URL(response.headers.get("location"), base).pathname, `/${locale}/${canonical}`);
  }
  for (const [path, destination] of [["merchant/apply", form], ["login/merchant", "https://app.qidaigo.com/login"], ["merchant", "https://app.qidaigo.com/login"]]) {
    const result = await get(`/${locale}/${path}?token=synthetic`);
    assert.equal(result.status, 307);
    assert.equal(result.headers.get("location"), destination);
  }
  const login = await page(`/${locale}/login`);
  assert.ok(login.includes("noindex"));
  const partner = await page(`/${locale}/partner/login`);
  assert.ok(!partner.includes('href="https://app.qidaigo.com/login"'), "partner page must not offer merchant login");
  for (const path of ["admin", "admin/platform", "api/public/leads", "api/auth/dev-login", "internal/projects", "partner/credits", "dashboard", "%61dmin", "products/unknown"]) {
    const result = await get(`/${locale}/${path}`);
    assert.equal(result.status, 404, path);
    assert.match(result.headers.get("cache-control"), /no-store/);
    assert.match(result.headers.get("x-robots-tag"), /noindex/);
  }
}
for (const path of ["/api/public/leads", "/en/api/public/leads", "/ja/api/auth/dev-login"]) assert.equal((await get(path, {}, "POST")).status, 404);
for (const path of ["/icon.svg", "/robots.txt"]) assert.equal((await get(path)).status, 200, path);
const result = { state: "passed", observed_at: new Date().toISOString(), base_url: base, localized_routes: routes.length, checks, browser_qa: "not_performed_by_http_smoke", mail_sent: false, form_submissions: 0, database_mutations: 0 };
if (evidencePath) await writeFile(evidencePath, JSON.stringify(result, null, 2) + "\n");
console.log(JSON.stringify({ state: result.state, localized_routes: routes.length, page_checks: checks.length }));
