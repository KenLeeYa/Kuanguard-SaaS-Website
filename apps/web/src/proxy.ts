import { NextResponse, type NextRequest } from "next/server";
import { deploymentSurface } from "./lib/surface";
import { commercePaths } from "./lib/commerce";

const internalRoots = new Set(["overview", "portfolio", "imports", "review", "dispatch", "crm", "billing", "integrations", "audit", "settings", "shc", "pt", "source", "templates", "question-banks", "phishing-operations", "customers", "retests", "changes", "tickets"]);
export function proxy(request: NextRequest) {
  const surface = deploymentSurface();
  const url = request.nextUrl.clone();
  let path: string;
  try { path = new URL(decodeURIComponent(url.pathname), "http://route-policy.invalid").pathname; }
  catch { return new NextResponse("Invalid path", { status: 400, headers: { "Cache-Control": "private, no-store" } }); }
  const root = path.split("/")[1];
  if (root === "products" && !commercePaths.includes(path.replace(/\/$/, "").slice(1))) return new NextResponse("Not found", { status: 404, headers: { "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow" } });
  const host = (request.headers.get("host") || "").split(":")[0].toLowerCase();
  const isAdmin = path === "/admin" || path.startsWith("/admin/") || internalRoots.has(root);
  const internalApi = path === "/api/internal" || path.startsWith("/api/internal/") || path === "/internal" || path.startsWith("/internal/") || path === "/api/platform" || path.startsWith("/api/platform/");
  if (surface === "public" && (isAdmin || internalApi || host === "admin.kuanguard.com")) return new NextResponse("Not found", { status: 404, headers: { "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow" } });
  if (host === "www.kuanguard.com") { url.hostname = "kuanguard.com"; url.port = ""; url.protocol = "https:"; return NextResponse.redirect(url, 308); }
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
export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico|fonts/|sitemap.xml|robots.txt).*)"] };
