import type { Metadata } from "next";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { publicPaths, services } from "@/lib/catalog";
import { commercePaths, commerceTitles, solutions } from "@/lib/commerce";
import { deploymentSurface } from "@/lib/surface";
import { apiOrigin, portalHeaders } from "@/lib/server-api";
import { AnnualPage, CoursesPage, InfoPage, QuotePage, ServicePage, ServicesPage } from "@/components/public-site";
import { CommerceFooter, CommerceHeader, CommerceHome, CommerceInfo, FeaturesPage, LeadPage, PartnersPage, PricingPage, SolutionPage } from "@/components/commerce-site";
import { WorkspacePage } from "@/components/workspace";
import { LoginRouter, MerchantEntry, PartnerPortal, PlatformAdmin } from "@/components/partner-portal";

type Props = { params: Promise<{ path?: string[] }>; searchParams: Promise<Record<string, string | string[] | undefined>> };
export const dynamic = "force-dynamic";
async function publicData(path: string) {
  const host = (await headers()).get("host") || "127.0.0.1:3180";
  try { const response = await fetch(new URL(path, apiOrigin()), { cache: "no-store", headers: portalHeaders(host, "GET", path), signal: AbortSignal.timeout(5000) }); return response.ok ? await response.json() : null; }
  catch { return null; }
}
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const path = (await params).path?.join("/") || "";
  const host = ((await headers()).get("host") || "").split(":")[0];
  const isPublic = (commercePaths.includes(path) || publicPaths.includes(path) || path.startsWith("courses/")) && ["kuanguard.com", "www.kuanguard.com", "127.0.0.1", "localhost"].includes(host);
  const service = services.find(s => path === `services/${s.slug}`);
  const solution = solutions.find(s => path === `solutions/${s.slug}`);
  const title = commerceTitles[path] || solution?.name || service?.name || (path.startsWith("partner") ? "合作夥伴工作空間" : "企業工作空間");
  const brand = path.startsWith("partner") ? (await publicData("/public/portal"))?.partner : null;
  return { title: brand?.branding?.company_name || title, alternates: isPublic ? { canonical: `https://kuanguard.com/${path}` } : undefined,
    openGraph: isPublic ? { title, url: `https://kuanguard.com/${path}`, siteName: "KUANGUARD", locale: "zh_TW", type: "website" } : undefined,
    icons: brand?.branding?.favicon_asset_id ? { icon: `/api/public/branding/${brand.id}/${brand.branding.favicon_asset_id}` } : undefined,
    robots: isPublic ? { index: true, follow: true } : { index: false, follow: false } };
}
export default async function Page({ params, searchParams }: Props) {
  const path = (await params).path?.join("/") || "";
  const query = await searchParams;
  if (path.startsWith("admin") && deploymentSurface() === "public") notFound();
  if (path.startsWith("admin/platform")) return <PlatformAdmin section={path.split("/")[2]} />;
  if (path.startsWith("partner/workspace/")) return <WorkspacePage path={path.replace("partner/workspace/", "admin/")} />;
  if (path === "partner" || (path.startsWith("partner/") && path !== "partner/login")) {
    if (!["partner", "partner/customers", "partner/credits", "partner/branding", "partner/domains", "partner/audit", "partner/commissions"].includes(path)) notFound();
    const portal = await publicData("/public/portal");
    if (!portal) notFound();
    return <PartnerPortal path={path} />;
  }
  const isPublic = commercePaths.includes(path) || publicPaths.includes(path) || path.startsWith("courses/") || path.startsWith("login") || path === "partner/login" || path === "merchant";
  if (!isPublic) {
    if (!["dashboard", "projects", "calendar", "assets", "findings", "reports", "phishing", "training", "wallet", "quotes", "contracts", "orders", "organization", "support", "learn", "onboarding", "entitlements", "questionnaires", "notifications", "admin"].includes(path.split("/")[0])) notFound();
    return <WorkspacePage path={path} />;
  }
  const product = ["", "features", "pricing", "merchant"].includes(path) ? await publicData("/public/commerce") : null;
  let content;
  if (!path) content = <CommerceHome product={product} />;
  else if (path === "features") content = <FeaturesPage product={product} />;
  else if (path === "pricing") content = <PricingPage product={product} />;
  else if (path === "partners") content = <PartnersPage />;
  else if (path.startsWith("solutions/") && solutions.some(s => s.slug === path.split("/")[1])) content = <SolutionPage slug={path.split("/")[1]} />;
  else if (path === "merchant/apply") content = <LeadPage />;
  else if (path === "contact") content = <LeadPage kind={query.kind === "partner" ? "partner" : "enterprise"} />;
  else if (path === "merchant") content = <MerchantEntry product={product} />;
  else if (path.startsWith("login") || path === "partner/login") content = <LoginRouter mode={path === "partner/login" ? "partner" : path.split("/")[1]} intent={typeof query.intent === "string" ? query.intent : undefined} partnerSlug={typeof query.partner === "string" ? query.partner : undefined} />;
  else if (commercePaths.includes(path)) content = <CommerceInfo path={path} />;
  else if (path === "services") content = <ServicesPage />;
  else if (path.startsWith("services/")) content = <ServicePage slug={path.split("/")[1]} />;
  else if (path === "plans/annual-security") content = <AnnualPage />;
  else if (path === "request-quote") content = <QuotePage />;
  else if (path.startsWith("courses")) content = <CoursesPage slug={path.split("/")[1]} />;
  else content = <InfoPage path={path} />;
  const schema = { "@context": "https://schema.org", "@type": "Organization", name: "KUANGUARD", url: "https://kuanguard.com", description: "商家營運 SaaS 與合作夥伴服務平台" };
  return <><CommerceHeader /><main id="main-content">{content}</main><CommerceFooter />{!path && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema).replace(/</g, "\\u003c") }} />}</>;
}
