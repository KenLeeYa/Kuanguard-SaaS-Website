/**
 * REVIEW PROPOSAL ONLY. This file is not installed in QIDAIGO.
 * Wire the source's existing authenticated grant verifier and minimal aggregate
 * queries after review. Never pass through getAdminBillingOverview's full return.
 */
import { createHmac } from "node:crypto";

type MetricKey = "gmv" | "platform_fees_accrued" | "platform_fees_received" | "refunds";
type VerifiedGrant = {
  issuer: "qidaigo-summary";
  audience: "kuanguard-portfolio";
  subject: "portfolio-readonly";
  id: string;
  product: "qidaigo";
  environment: string;
  scope: "portfolio.summary.read";
  tenantScope: string;
  expiresAt: number;
  active: boolean;
};
type AggregateMetric = {
  key: MetricKey;
  value: number | null;
  currency: string;
  tax_basis: "inclusive" | "exclusive" | "unknown";
  period_start: string;
  period_end: string;
  timezone: string;
  verified: boolean;
};
type Dependencies = {
  environment: string;
  responseSigningKey: string;
  // Must verify algorithm, signature, issuer, audience, exp/iat and active grant.
  verifyReadOnlyGrant(token: string): Promise<VerifiedGrant>;
  // This source-side implementation must SELECT aggregate columns only.
  readApprovedAggregates(grant: VerifiedGrant): Promise<{
    sourceAt: string;
    metrics: AggregateMetric[];
    complete: boolean;
    tasksOpen: number | null;
    tasksOverdue: number | null;
    health: "healthy" | "degraded" | "unknown";
  }>;
};

const KEYS = new Set<MetricKey>(["gmv", "platform_fees_accrued", "platform_fees_received", "refunds"]);
const headers = { "Cache-Control": "no-store", "Content-Type": "application/json" };

export function createPortfolioSummaryGet(deps: Dependencies) {
  if (deps.responseSigningKey.length < 32) throw new Error("Dedicated response signing key required");
  return async function GET(request: Request): Promise<Response> {
    if (request.method !== "GET") return new Response("{}", { status: 405, headers });
    const url = new URL(request.url);
    if (url.search) return new Response("{}", { status: 422, headers });
    const nonce = request.headers.get("X-Portfolio-Nonce") ?? "";
    if (!/^[a-zA-Z0-9_-]{16,100}$/.test(nonce)) return new Response("{}", { status: 400, headers });
    const authorization = request.headers.get("Authorization") ?? "";
    if (!authorization.startsWith("Bearer ")) return new Response("{}", { status: 401, headers });
    let grant: VerifiedGrant;
    try {
      grant = await deps.verifyReadOnlyGrant(authorization.slice(7));
    } catch {
      return new Response("{}", { status: 401, headers });
    }
    if (!grant.active || grant.product !== "qidaigo" || grant.environment !== deps.environment ||
        grant.scope !== "portfolio.summary.read" || grant.subject !== "portfolio-readonly" ||
        grant.issuer !== "qidaigo-summary" || grant.audience !== "kuanguard-portfolio" ||
        grant.expiresAt <= Math.floor(Date.now() / 1000)) {
      return new Response("{}", { status: 403, headers });
    }
    try {
      const source = await deps.readApprovedAggregates(grant);
      const metrics = source.metrics.map((metric) => {
        if (!KEYS.has(metric.key) || (metric.value !== null && (!Number.isSafeInteger(metric.value) || metric.value < 0))) {
          throw new Error("Invalid approved metric");
        }
        // Deliberate field projection excludes all accidental/raw source fields.
        return { key: metric.key, value: metric.value, currency: metric.currency,
          tax_basis: metric.tax_basis, period_start: metric.period_start, period_end: metric.period_end,
          timezone: metric.timezone, verified: metric.verified, unit: "minor_currency",
          definition_version: `qidaigo.${metric.key}/1`, measurement: "flow" };
      });
      const body = JSON.stringify({ schema_version: "portfolio.summary/1", product: "qidaigo",
        environment: deps.environment, scope: "portfolio.summary.read", tenant_scope: grant.tenantScope,
        grant_id: grant.id, source_at: source.sourceAt, complete: source.complete, synthetic: false,
        metrics, health: source.health, tasks_open: source.tasksOpen, tasks_overdue: source.tasksOverdue });
      if (Buffer.byteLength(body, "utf8") > 128 * 1024) throw new Error("Summary size exceeded");
      const timestamp = String(Math.floor(Date.now() / 1000));
      const signature = createHmac("sha256", deps.responseSigningKey)
        .update(`${timestamp}\n${nonce}\n${body}`).digest("hex");
      return new Response(body, { status: 200, headers: { ...headers,
        "X-Portfolio-Timestamp": timestamp, "X-Portfolio-Signature": signature } });
    } catch {
      // Do not leak customer data, SQL or secrets in the error body.
      return new Response("{}", { status: 503, headers });
    }
  };
}
