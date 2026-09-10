import Link from "next/link";
export default function NotFound() { return <main id="main-content" className="state-box" style={{ minHeight: "100vh" }}><strong>找不到此頁面</strong><p>網址可能已變更，或此部署不提供這個入口。</p><Link className="button" href="/">返回首頁</Link></main>; }
