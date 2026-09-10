import { type NextRequest } from "next/server";
import { deploymentSurface } from "@/lib/surface";
import { apiOrigin, portalHeaders } from "@/lib/server-api";

export const dynamic = "force-dynamic";
type Context = { params: Promise<{ path: string[] }> };
async function forward(request: NextRequest, context: Context) {
  const { path } = await context.params;
  if (path.some(part => part === "." || part === ".." || /[\\/\x00]/.test(part))) return new Response("Invalid path", { status: 400 });
  if (deploymentSurface() === "public" && ["internal", "platform"].includes(path[0])) return new Response("Not found", { status: 404 });
  let origin: URL;
  try { origin = apiOrigin(); } catch { return new Response("Invalid API binding", { status: 503 }); }
  const target = new URL(path.map(encodeURIComponent).join("/"), origin);
  target.search = request.nextUrl.search;
  const headers = new Headers();
  for (const key of ["cookie", "origin", "content-type", "x-csrf-token", "idempotency-key", "cf-access-jwt-assertion", "user-agent", "access-control-request-method", "access-control-request-headers", "x-payment-timestamp", "x-payment-signature"]) {
    const value = request.headers.get(key); if (value) headers.set(key, value);
  }
  // The same-origin gateway forwards the actual Host, never caller-supplied X-Forwarded-Host.
  try { for (const [key, value] of Object.entries(portalHeaders(request.headers.get("host") || "", request.method, target.pathname + target.search))) headers.set(key, value); }
  catch { return Response.json({ detail: { code: "PORTAL_PROXY_PENDING", message: "網站入口尚未完成安全代理設定。" } }, { status: 503 }); }
  let body: ArrayBuffer | undefined;
  if (!["GET", "HEAD"].includes(request.method)) {
    const declared = Number(request.headers.get("content-length") || 0);
    if (!Number.isFinite(declared) || declared > 6000000) return new Response("Payload too large", { status: 413 });
    body = await request.arrayBuffer();
    if (body.byteLength > 6000000) return new Response("Payload too large", { status: 413 });
  }
  try {
    const upstream = await fetch(target, { method: request.method, headers, body, cache: "no-store", redirect: "manual", signal: AbortSignal.timeout(30000) });
    const outgoing = new Headers();
    for (const key of ["content-type", "content-disposition", "location", "x-request-id", "x-content-type-options", "access-control-allow-origin", "access-control-allow-credentials", "access-control-allow-methods", "access-control-allow-headers"]) {
      const value = upstream.headers.get(key); if (value) outgoing.set(key, value);
    }
    for (const cookie of upstream.headers.getSetCookie()) outgoing.append("set-cookie", cookie);
    outgoing.set("cache-control", "private, no-store"); outgoing.set("x-robots-tag", "noindex, nofollow"); outgoing.set("referrer-policy", "no-referrer"); outgoing.set("vary", "Cookie, Origin, Host");
    return new Response(upstream.body, { status: upstream.status, headers: outgoing });
  } catch { return Response.json({ detail: { code: "API_UNAVAILABLE", message: "服務暫時無法連線，請稍後重試。" } }, { status: 503, headers: { "Cache-Control": "no-store" } }); }
}
export { forward as GET, forward as POST, forward as PUT, forward as PATCH, forward as DELETE, forward as HEAD, forward as OPTIONS };
