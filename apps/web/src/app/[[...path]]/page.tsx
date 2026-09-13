import type { Metadata } from "next";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { publicPaths, services } from "@/lib/catalog";
import { commerceDescriptions, commercePaths, commerceTitles, solutions } from "@/lib/commerce";
import { deploymentSurface } from "@/lib/surface";
import { apiOrigin, portalHeaders } from "@/lib/server-api";
import { AnnualPage, CoursesPage, InfoPage, QuotePage, ServicePage, ServicesPage } from "@/components/public-site";
import { CommerceFooter, CommerceHeader, CommerceHome, CommerceInfo, FeaturesPage, LeadPage, PricingPage, SolutionPage } from "@/components/commerce-site";
import { WorkspacePage } from "@/components/workspace";
import { LoginRouter, MerchantEntry, PartnerPortal, PlatformAdmin } from "@/components/partner-portal";
import { CorporateFooter, CorporateHeader, CorporateHome, CorporatePartners, CorporateProducts, CorporateSolutions, OrderingBreadcrumb } from "@/components/corporate-site";
import { isWebsitePath, websiteContactEmail, websiteEntryPaths, websiteOnly } from "@/lib/website";
import { WebsiteContact, WebsiteEntry } from "@/components/website-contact";
import websiteCommerce from "@/lib/website-commerce.json";
import { splitLocale, languageAlternates, localePath, openGraphLocales } from "@/lib/locales";
import { translate } from "@/lib/translate";
import { websiteInfo } from "@/lib/website-info";
import { WebsiteInfo } from "@/components/website-info";

type Props = { params: Promise<{ path?: string[] }>; searchParams: Promise<Record<string, string | string[] | undefined>> };
export const dynamic = "force-dynamic";
async function publicData(path: string) {
  if (websiteOnly()) return path === "/public/commerce" ? websiteCommerce : null;
  const host = (await headers()).get("host") || "127.0.0.1:3180";
  try { const response = await fetch(new URL(path, apiOrigin()), { cache: "no-store", headers: portalHeaders(host, "GET", path), signal: AbortSignal.timeout(5000) }); return response.ok ? await response.json() : null; }
  catch { return null; }
}
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const requested = (await params).path?.join("/") || "";
  const { path, locale = "zh-TW" } = websiteOnly() ? splitLocale(requested) : { path: requested };
  const host = ((await headers()).get("host") || "").split(":")[0];
  const isPublic = (commercePaths.includes(path) || publicPaths.includes(path) || path.startsWith("courses/")) && ["kuanguard.com", "www.kuanguard.com", "127.0.0.1", "localhost"].includes(host);
  const service = services.find(s => path === `services/${s.slug}`);
  const solution = solutions.find(s => path === `solutions/${s.slug}`);
  if (websiteOnly()) {
    const label = commerceTitles[path] || websiteInfo[path]?.title || solution?.name || service?.name || ({ services: "企業資安服務", "plans/annual-security": "年度整合方案", "request-quote": "洽詢企業資安服務", courses: "課程目錄準備中" } as Record<string, string>)[path] || "選擇你的系統";
    const title = translate(label, locale);
    const description = translate(commerceDescriptions[path] || websiteInfo[path]?.description || solution?.description || service?.description || "探索 KUANGUARD 的產品、服務與平台入口。", locale);
    const url = `https://kuanguard.com${localePath(`/${path}`, locale)}`;
    const index = isWebsitePath(path) && !websiteEntryPaths.includes(path) && path !== "courses" && ["kuanguard.com", "www.kuanguard.com", "127.0.0.1", "localhost"].includes(host);
    return { title, description, alternates: { canonical: url, languages: languageAlternates(path) }, openGraph: { title, description, url, siteName: "KUANGUARD", locale: openGraphLocales[locale], alternateLocale: Object.values(openGraphLocales).filter(value => value !== openGraphLocales[locale]), type: "website" }, twitter: { card: "summary", title, description }, robots: { index, follow: index } };
  }
  const title = commerceTitles[path] || solution?.name || service?.name || (path.startsWith("partner") ? "合作夥伴工作空間" : "企業工作空間");
  const brand = path.startsWith("partner") ? (await publicData("/public/portal"))?.partner : null;
  return { title: brand?.branding?.company_name || title, description: commerceDescriptions[path], alternates: isPublic ? { canonical: `https://kuanguard.com/${path}` } : undefined,
    openGraph: isPublic ? { title, description: commerceDescriptions[path], url: `https://kuanguard.com/${path}`, siteName: "KUANGUARD", locale: "zh_TW", type: "website" } : undefined,
    icons: brand?.branding?.favicon_asset_id ? { icon: `/api/public/branding/${brand.id}/${brand.branding.favicon_asset_id}` } : undefined,
    robots: isPublic ? { index: true, follow: true } : { index: false, follow: false } };
}
export default async function Page({ params, searchParams }: Props) {
  const requested = (await params).path?.join("/") || "";
  const { path, locale = "zh-TW" } = websiteOnly() ? splitLocale(requested) : { path: requested };
  const query = await searchParams;
  if (websiteOnly()) {
    if (!isWebsitePath(path)) notFound();
    const contactTitle = path === "merchant/apply" ? "申請商家產品諮詢" : path === "request-quote" ? "洽詢企業資安服務" : query.kind === "partner" ? "系統合作諮詢" : "聯絡 KUANGUARD";
    const standalone = ["contact", "merchant/apply", "request-quote"].includes(path)
      ? <WebsiteContact email={websiteContactEmail} title={contactTitle} />
      : websiteEntryPaths.includes(path) || path === "courses" ? <WebsiteEntry email={websiteContactEmail} courses={path === "courses"} product={["login/partner", "partner/login"].includes(path) ? "partner" : path === "login/customer" ? "security" : undefined} /> : websiteInfo[path] ? <WebsiteInfo path={path} /> : null;
    if (standalone) return <><CorporateHeader /><main id="main-content" className="kg-corporate-surface">{standalone}</main><CorporateFooter /></>;
  }
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
  const merchantPage = ["products/ordering", "features", "pricing", "merchant/apply"].includes(path) || solutions.some(solution => path === `solutions/${solution.slug}`);
  const product = ["products/ordering", "features", "pricing", "merchant"].includes(path) ? await publicData("/public/commerce") : null;
  let content;
  if (!path) content = <CorporateHome />;
  else if (path === "products") content = <CorporateProducts />;
  else if (path === "products/ordering") content = <CommerceHome product={product} />;
  else if (path === "solutions") content = <CorporateSolutions />;
  else if (path === "features") content = <FeaturesPage product={product} />;
  else if (path === "pricing") content = <PricingPage product={product} />;
  else if (path === "partners") content = <CorporatePartners />;
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
  const schema = { "@context": "https://schema.org", "@type": "Organization", name: "KUANGUARD", url: "https://kuanguard.com", email: websiteContactEmail, description: translate("數位產品與系統合作", locale) };
  return <>{merchantPage ? <CommerceHeader /> : <CorporateHeader />}{merchantPage && <OrderingBreadcrumb path={path} />}<main id="main-content" className={merchantPage ? undefined : "kg-corporate-surface"}>{content}</main>{merchantPage ? <CommerceFooter /> : <CorporateFooter />}{!path && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema).replace(/</g, "\\u003c") }} />}</>;
}
