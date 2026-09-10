import type { Metadata } from "next";
import { SessionProvider } from "@/lib/api";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://kuanguard.com"),
  title: { default: "KUANGUARD｜企業資安服務平台", template: "%s｜KUANGUARD" },
  description: "整合七項企業資安服務、專業交付、社交工程演練與線上教育訓練，從檢測到改善持續留存紀錄。",
  openGraph: { siteName: "KUANGUARD", type: "website", locale: "zh_TW" },
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="zh-Hant-TW"><body><a className="skip-link" href="#main-content">跳至主要內容</a><SessionProvider>{children}</SessionProvider></body></html>; }
