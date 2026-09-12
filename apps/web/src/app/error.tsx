"use client";
import { Localized } from "@/components/website-language";
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) { return <Localized><main id="main-content" className="state-box"><h1>此頁面暫時無法載入</h1><p>請稍後重試，或透過聯絡信箱告訴我們。</p><button className="button" onClick={reset}>重新載入</button></main></Localized>; }
