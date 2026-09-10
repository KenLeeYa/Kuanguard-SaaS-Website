import type { Metadata } from "next";
import { SessionProvider } from "@/lib/api";
import { websiteOnly } from "@/lib/website";
import "./globals.css";
import "./commerce.css";
import "./corporate.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://kuanguard.com"),
  title: { default: "KUANGUARD｜數位科技、產品與平台服務", template: "%s｜KUANGUARD" },
  description: "KUANGUARD 以數位科技連接產品、資訊與人，提供商家 SaaS、合作夥伴平台與企業資安服務。從實際工作出發，找到合適的數位工具與協作方式。",
  openGraph: { siteName: "KUANGUARD", type: "website", locale: "zh_TW" },
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="zh-Hant-TW"><body><a className="skip-link" href="#main-content">跳至主要內容</a>{websiteOnly() ? children : <SessionProvider>{children}</SessionProvider>}</body></html>; }
