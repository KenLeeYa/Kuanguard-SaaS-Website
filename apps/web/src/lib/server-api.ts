import { createHmac } from "node:crypto";

export function apiOrigin() {
  const origin = new URL(process.env.API_INTERNAL_URL || "http://127.0.0.1:8180");
  if (!["http:", "https:"].includes(origin.protocol) || origin.username || origin.password || origin.search || origin.hash || origin.pathname !== "/" || origin.hostname === "qidaigo.com" || origin.hostname.endsWith(".qidaigo.com")) throw new Error("Invalid API binding");
  if (process.env.VERCEL && (origin.protocol !== "https:" || origin.hostname !== "api.kuanguard.com" || !process.env.PORTAL_PROXY_SECRET)) throw new Error("Verified HTTPS API and BFF signing key required");
  return origin;
}
export function portalHeaders(host: string, method: string, path: string): Record<string, string> {
  const secret = process.env.PORTAL_PROXY_SECRET;
  if (!secret) throw new Error("BFF signing key is required to preserve the authenticated host");
  const timestamp = String(Math.floor(Date.now() / 1000));
  const signature = createHmac("sha256", secret).update(`${method}\n${path}\n${host}\n${timestamp}`).digest("hex");
  return { "x-kg-portal-host": host, "x-kg-portal-time": timestamp, "x-kg-portal-signature": signature };
}
