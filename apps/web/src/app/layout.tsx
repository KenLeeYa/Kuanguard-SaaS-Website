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
  title: { default: "KUANGUARD｜數位產品與系統合作介紹", template: "%s｜KUANGUARD" },
  description: "探索 KUANGUARD 的餐飲、美業與學習服務方向，了解跨領域系統合作、商家曝光與服務介接的合作規劃。",
  openGraph: { siteName: "KUANGUARD", type: "website", locale: "zh_TW" },
};
export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const selected = (await headers()).get("x-website-locale") || "zh-TW";
  const locale = websiteOnly() && isLocale(selected) ? selected : "zh-TW";
  return <html lang={locale}><body><a className="skip-link" href="#main-content">{translate("跳至主要內容", locale)}</a>{websiteOnly() ? <WebsiteLanguage locale={locale}>{children}</WebsiteLanguage> : <SessionProvider>{children}</SessionProvider>}</body></html>;
}
