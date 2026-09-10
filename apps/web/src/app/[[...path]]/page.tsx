import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { publicPaths, services } from "@/lib/catalog";
import { deploymentSurface } from "@/lib/surface";
import { AnnualPage, CoursesPage, HomePage, InfoPage, PublicFooter, PublicHeader, QuotePage, ServicePage, ServicesPage } from "@/components/public-site";
import { LoginPage, WorkspacePage } from "@/components/workspace";

type Props = { params: Promise<{ path?: string[] }> };
export const dynamic = "force-dynamic";
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const path = (await params).path?.join("/") || "";
  const isPublic = publicPaths.includes(path) || path.startsWith("courses/");
  const service = services.find(s => path === `services/${s.slug}`);
  const names: Record<string, string> = { services: "七項核心資安服務", "request-quote": "服務需求與詢價", courses: "線上教育訓練", "plans/annual-security": "年度整合方案", trust: "信任中心", resources: "資源中心", "pricing/credits": "點數與計費", login: "登入", dashboard: "企業工作台", learn: "我的學習" };
  return { title: service?.name || names[path] || (path ? "企業資安服務平台" : "KUANGUARD｜企業資安服務平台"), alternates: isPublic ? { canonical: `https://kuanguard.com/${path}` } : undefined, robots: isPublic ? { index: true, follow: true } : { index: false, follow: false } };
}
export default async function Page({ params }: Props) {
  const path = (await params).path?.join("/") || "";
  if (path.startsWith("admin") && deploymentSurface() === "public") notFound();
  const isPublic = publicPaths.includes(path) || path.startsWith("courses/") || path === "login";
  if (!isPublic) {
    if (!["dashboard", "projects", "calendar", "assets", "findings", "reports", "phishing", "training", "wallet", "quotes", "contracts", "orders", "organization", "support", "learn", "onboarding", "entitlements", "questionnaires", "notifications", "admin"].includes(path.split("/")[0])) notFound();
    return <WorkspacePage path={path} />;
  }
  let content;
  if (!path) content = <HomePage />;
  else if (path === "services") content = <ServicesPage />;
  else if (path.startsWith("services/")) content = <ServicePage slug={path.split("/")[1]} />;
  else if (path === "plans/annual-security") content = <AnnualPage />;
  else if (path === "request-quote") content = <QuotePage />;
  else if (path.startsWith("courses")) content = <CoursesPage slug={path.split("/")[1]} />;
  else if (path === "login") content = <LoginPage />;
  else content = <InfoPage path={path} />;
  return <><PublicHeader /><main id="main-content">{content}</main><PublicFooter /></>;
}
