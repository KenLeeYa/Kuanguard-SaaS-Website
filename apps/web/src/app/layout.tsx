import type { Metadata } from "next";
import { SessionProvider } from "@/lib/api";
import { websiteOnly } from "@/lib/website";
import { headers } from "next/headers";
import { isLocale } from "@/lib/locales";
import { translate } from "@/lib/translate";
import { WebsiteLanguage } from "@/components/website-language";
import "./globals.css";
import "./commerce.css";
import "./corporate.css";
import "./website.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://kuanguard.com"),
  title: { default: "KUANGUARD｜數位科技、產品與平台服務", template: "%s｜KUANGUARD" },
  description: "KUANGUARD 以數位科技連接產品、資訊與人，提供商家 SaaS、合作夥伴平台與企業資安服務。從實際工作出發，找到合適的數位工具與協作方式。",
  openGraph: { siteName: "KUANGUARD", type: "website", locale: "zh_TW" },
};
export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const selected = (await headers()).get("x-website-locale") || "zh-TW";
  const locale = websiteOnly() && isLocale(selected) ? selected : "zh-TW";
  return <html lang={locale}><body><a className="skip-link" href="#main-content">{translate("跳至主要內容", locale)}</a>{websiteOnly() ? <WebsiteLanguage locale={locale}>{children}</WebsiteLanguage> : <SessionProvider>{children}</SessionProvider>}</body></html>;
}
