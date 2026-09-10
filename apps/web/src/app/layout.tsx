import type { Metadata } from "next";
import { SessionProvider } from "@/lib/api";
import "./globals.css";
import "./commerce.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://kuanguard.com"),
  title: { default: "KUANGUARD｜讓每一筆生意，更好經營", template: "%s｜KUANGUARD" },
  description: "從線上點餐、QR Code 掃碼、預約與出單到多門市管理，KUANGUARD 陪伴商家整理日常，並與合作夥伴持續提供專業服務。",
  openGraph: { siteName: "KUANGUARD", type: "website", locale: "zh_TW" },
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="zh-Hant-TW"><body><a className="skip-link" href="#main-content">跳至主要內容</a><SessionProvider>{children}</SessionProvider></body></html>; }
