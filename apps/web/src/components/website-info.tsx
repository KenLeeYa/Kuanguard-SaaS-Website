"use client";
import { websiteInfo } from "@/lib/website-info";
import { stallOrder } from "@/lib/product-links";
import { CommerceIntro } from "./commerce-site";
import Link from "./guarded-link";
import { Localized } from "./website-language";

export function WebsiteInfo({ path }: { path: string }) {
  const info = websiteInfo[path];
  return <Localized><div className="commerce-site"><CommerceIntro eyebrow="KUANGUARD" title={info.title} description={info.description} /><article className="commerce-prose commerce-container">{info.paragraphs.map(paragraph => <p key={paragraph}>{paragraph}</p>)}<div className="website-info-links">{path === "resources" ? <><a href={stallOrder.website}>攤點通官方網站</a><Link href="/services">企業資安服務</Link><Link href="/plans/annual-security">年度整合方案</Link></> : <><Link href="/privacy">隱私權政策</Link><Link href="/terms">網站使用條款</Link><Link href="/security">資料安全</Link></>}<Link href="/contact">聯絡我們</Link></div></article></div></Localized>;
}
