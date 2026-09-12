"use client";
import Link from "@/components/guarded-link";
import { Localized } from "@/components/website-language";
export default function NotFound() { return <Localized><main id="main-content" className="state-box" style={{ minHeight: "70vh" }}><h1>找不到此頁面</h1><p>網址可能已變更，或此部署不提供這個入口。</p><Link className="button" href="/">返回首頁</Link></main></Localized>; }
