import { NextResponse, type NextRequest } from "next/server";
import { deploymentSurface } from "./lib/surface";
import { commercePaths } from "./lib/commerce";
import { isWebsitePath, websiteOnly, websiteAliases } from "./lib/website";
import { localeCookie, localePath, preferredLocale, splitLocale } from "./lib/locales";
import { publicDestination } from "./lib/product-links";
import { translate } from "./lib/translate";

const internalRoots = new Set(["overview", "portfolio", "imports", "review", "dispatch", "crm", "billing", "integrations", "audit", "settings", "shc", "pt", "source", "templates", "question-banks", "phishing-operations", "customers", "retests", "changes", "tickets"]);
export function proxy(request: NextRequest) {
  const surface = deploymentSurface();
  const url = request.nextUrl.clone();
  let path: string;
  try { path = new URL(decodeURIComponent(url.pathname), "http://route-policy.invalid").pathname; }
  catch { return new NextResponse("Invalid path", { status: 400, headers: { "Cache-Control": "private, no-store" } }); }
  const localized = websiteOnly() ? splitLocale(path) : { path: path.replace(/^\/|\/$/g, ""), locale: undefined };
  if (websiteOnly()) path = `/${localized.path}`;
  const root = path.split("/")[1];
  if (!websiteOnly() && root === "products" && !commercePaths.includes(path.replace(/\/$/, "").slice(1))) return new NextResponse("Not found", { status: 404, headers: { "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow" } });
  const host = (request.headers.get("host") || "").split(":")[0].toLowerCase();
  const isAdmin = path === "/admin" || path.startsWith("/admin/") || internalRoots.has(root);
  const internalApi = path === "/api/internal" || path.startsWith("/api/internal/") || path === "/internal" || path.startsWith("/internal/") || path === "/api/platform" || path.startsWith("/api/platform/");
  if (surface === "public" && (isAdmin || internalApi || host === "admin.kuanguard.com")) return new NextResponse("Not found", { status: 404, headers: { "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow" } });
  if (host === "www.kuanguard.com") { url.hostname = "kuanguard.com"; url.port = ""; url.protocol = "https:"; return NextResponse.redirect(url, 308); }
  if (websiteOnly()) {
    const locale = localized.locale || preferredLocale(request.headers.get("accept-language") || "", request.cookies.get(localeCookie)?.value);
    if (localized.path === "solutions/beauty") { url.pathname = localePath("/products", locale); url.search = ""; url.hash = "beauty"; return NextResponse.redirect(url, 308); }
    if (!isWebsitePath(path.replace(/\/$/, "").slice(1))) {
      const text = (value: string) => translate(value, locale).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
      return new NextResponse(`<!doctype html><html lang="${locale}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>404 · KUANGUARD</title></head><body style="margin:0;font-family:system-ui,sans-serif;color:#263c60;background:#f6f8fb"><main style="max-width:40rem;margin:12vh auto;padding:2rem"><p>KUANGUARD / 404</p><h1>${text("找不到此頁面")}</h1><p>${text("網址可能已變更，或此部署不提供這個入口。")}</p><a style="display:inline-block;padding:1rem;color:inherit" href="/${locale}">${text("返回首頁")}</a></main></body></html>`, { status: 404, headers: { "Content-Type": "text/html; charset=utf-8", "Content-Language": locale, "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow" } });
    }
    const destination = publicDestination(localized.path);
    if (destination) return NextResponse.redirect(destination, { status: 307, headers: { "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow" } });
    if (!localized.locale) {
      url.pathname = localePath(path, locale);
      return NextResponse.redirect(url, { status: 307, headers: { "Cache-Control": "private, no-store", Vary: "Accept-Language, Cookie" } });
    }
    if (websiteAliases[localized.path]) { url.pathname = localePath(`/${websiteAliases[localized.path]}`, locale); return NextResponse.redirect(url, 308); }
    const requestHeaders = new Headers(request.headers);
    requestHeaders.set("x-website-locale", locale);
    const response = NextResponse.next({ request: { headers: requestHeaders } });
    response.headers.set("Content-Language", locale);
    response.headers.set("Content-Security-Policy", "frame-ancestors 'none'; base-uri 'self'; object-src 'none'");
    if (!commercePaths.includes(path.slice(1)) && ["login", "partner", "merchant"].includes(root)) response.headers.set("X-Robots-Tag", "noindex, nofollow");
    return response;
  }
  if ((surface === "internal" || host === "admin.kuanguard.com") && !path.startsWith("/api/") && !path.startsWith("/internal/") && !path.startsWith("/admin") && path !== "/login") {
    url.pathname = path === "/" ? "/admin/overview" : `/admin${path}`;
    return NextResponse.rewrite(url, { headers: { "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow" } });
  }
  if (host === "app.kuanguard.com" && path === "/services") { url.pathname = "/entitlements"; return NextResponse.rewrite(url); }
  if (host === "app.kuanguard.com" && path === "/") { url.pathname = "/merchant"; return NextResponse.redirect(url); }
  const coreHosts = ["kuanguard.com", "www.kuanguard.com", "app.kuanguard.com", "admin.kuanguard.com", "auth.kuanguard.com", "localhost", "127.0.0.1", process.env.VERCEL_URL].filter(Boolean);
  if (!coreHosts.includes(host) && ["/", "/login"].includes(path)) { url.pathname = path === "/" ? "/partner" : "/partner/login"; return NextResponse.rewrite(url, { headers: { "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow" } }); }
  const response = NextResponse.next();
  if (isAdmin || internalApi || path.startsWith("/api/") || ["partner", "merchant", "dashboard", "projects", "calendar", "assets", "findings", "reports", "phishing", "training", "wallet", "quotes", "contracts", "orders", "organization", "support", "learn", "login", "onboarding", "entitlements", "questionnaires", "notifications"].includes(root)) {
    response.headers.set("Cache-Control", "private, no-store");
    response.headers.set("X-Robots-Tag", "noindex, nofollow");
  }
  return response;
}
export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico|icon.svg|fonts/|sitemap.xml|robots.txt).*)"] };
