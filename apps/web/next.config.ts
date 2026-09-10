import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    if (process.env.KUANGUARD_WEBSITE_ONLY === "true") return [];
    const api = process.env.API_INTERNAL_URL || "http://127.0.0.1:8180";
    const target = new URL(api);
    if (target.username || target.password || target.search || target.hash || target.pathname !== "/") throw new Error("API_INTERNAL_URL must be an origin without credentials, path, query, or fragment");
    if (target.hostname === "qidaigo.com" || target.hostname.endsWith(".qidaigo.com")) throw new Error("KUANGUARD cannot use a QIDAIGO API origin");
    if (process.env.VERCEL && (target.protocol !== "https:" || target.hostname !== "api.kuanguard.com")) throw new Error("Vercel requires the verified KUANGUARD HTTPS API origin");
    return [
      { source: "/internal/:path*", destination: `${api.replace(/\/$/, "")}/internal/:path*` },
    ];
  },
  async headers() {
    return [
      { source: "/:path*", headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      ] },
      { source: "/api/:path*", headers: [{ key: "Cache-Control", value: "private, no-store" }, { key: "X-Robots-Tag", value: "noindex, nofollow" }] },
    ];
  },
};
export default nextConfig;
