"use client";

import { useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { ArrowRight, ArrowUpRight, Blocks, Check, ChevronRight, FileCheck2, KeyRound, Menu, Network, ShieldCheck, Store, Workflow, X } from "lucide-react";
import Link from "./guarded-link";
import { CommerceBrand } from "./commerce-site";

const products = [
  { id: "01", category: "MERCHANT SAAS", name: "商家點餐系統", description: "從掃碼點餐、預約到出單與門市管理，讓每一天的營運更有條理。", href: "/products/ordering", action: "探索點餐產品", kind: "ordering", tags: ["線上點餐", "預約出單", "門市管理"] },
  { id: "02", category: "PARTNER PLATFORM", name: "合作夥伴平台", description: "連接客戶、專案與服務交付，用自己的品牌，建立持續協作的工作空間。", href: "/partners", action: "認識 Partner 平台", kind: "partner", tags: ["客戶歸屬", "專案協作", "品牌入口"] },
  { id: "03", category: "SECURITY SERVICES", name: "企業資安服務", description: "從風險檢測到報告、改善與教育訓練，讓專業判斷成為可以追蹤的行動。", href: "/services", action: "了解資安服務", kind: "security", tags: ["檢測評估", "改善追蹤", "教育訓練"] },
];
const audiences = [
  { id: "01", title: "商家與門市", text: "把接單、顧客服務與門市作業整理在一起，從每天最常使用的流程開始。", href: "/products/ordering", label: "探索商家產品", icon: Store },
  { id: "02", title: "企業與團隊", text: "掌握資訊風險、釐清改善順序，讓檢測、交付與團隊學習有跡可循。", href: "/services", label: "了解企業服務", icon: ShieldCheck },
  { id: "03", title: "專業服務夥伴", text: "保留自己的品牌與客戶關係，透過共同的平台管理專案、授權與服務。", href: "/partners", label: "認識合作模式", icon: Network },
];

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <span className="kg-eyebrow"><span aria-hidden="true" />{children}</span>;
}
function Action({ href, children, secondary = false }: { href: string; children: React.ReactNode; secondary?: boolean }) {
  return <Link className={`kg-button${secondary ? " kg-button-secondary" : ""}`} href={href}>{children}<ArrowUpRight size={17} aria-hidden="true" /></Link>;
}
export function CorporateHeader() {
  const [open, setOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const path = usePathname();
  const navigation = [["/products", "產品與平台"], ["/solutions", "解決方案"], ["/partners", "合作夥伴"], ["/about", "關於我們"]];
  return <header className="kg-header" onKeyDown={event => { if (event.key === "Escape" && open) { setOpen(false); menuButton.current?.focus(); } }}>
    <div className="kg-container kg-header-inner">
      <CommerceBrand />
      <button ref={menuButton} className="kg-menu-button" aria-label={open ? "關閉主要選單" : "開啟主要選單"} aria-expanded={open} aria-controls="corporate-navigation" onClick={() => setOpen(!open)}>{open ? <X size={21} /> : <Menu size={21} />}</button>
      <nav id="corporate-navigation" className={open ? "is-open" : ""} aria-label="主要導覽" onClick={() => setOpen(false)}>
        {navigation.map(([href, label]) => <Link key={href} href={href} aria-current={path === href ? "page" : undefined}>{label}</Link>)}
        <span className="kg-nav-actions"><Link href="/login">平台登入<ArrowUpRight size={13} aria-hidden="true" /></Link><Action href="/contact">聯絡我們</Action></span>
      </nav>
    </div>
  </header>;
}
export function CorporateFooter() {
  return <footer className="kg-footer"><div className="kg-container">
    <div className="kg-footer-grid"><div className="kg-footer-brand"><CommerceBrand /><p>數位科技，走進每一天的營運。<br />從產品、資訊到人，連接工作的每一步。</p></div>
      <div><strong>產品與服務</strong><Link href="/products/ordering">商家點餐系統</Link><Link href="/partners">合作夥伴平台</Link><Link href="/services">企業資安服務</Link><Link href="/products">查看所有產品</Link></div>
      <div><strong>探索 KUANGUARD</strong><Link href="/about">關於我們</Link><Link href="/solutions">解決方案</Link><Link href="/contact">聯絡我們</Link><Link href="/security">資料安全</Link></div>
      <div><strong>服務入口</strong><Link href="/login">平台登入</Link><Link href="/partner/login">合作夥伴登入</Link><Link href="/merchant/apply">商家產品申請</Link></div>
    </div>
    <div className="kg-footer-bottom"><span>© {new Date().getFullYear()} KUANGUARD</span><span>臺灣 · 繁體中文</span><div><Link href="/privacy">隱私權政策</Link><Link href="/terms">服務條款</Link></div></div>
  </div></footer>;
}
export function OrderingBreadcrumb({ path }: { path: string }) {
  return <nav className="kg-product-breadcrumb" aria-label="產品位置"><div className="commerce-container"><Link href="/">KUANGUARD 數位科技</Link><ChevronRight size={13} aria-hidden="true" /><Link href="/products">旗下產品</Link><ChevronRight size={13} aria-hidden="true" /><Link href="/products/ordering" aria-current={path === "products/ordering" ? "page" : undefined}>商家點餐系統</Link></div></nav>;
}

function TechnologyVisual() {
  return <div className="kg-technology" aria-label="KUANGUARD 旗下產品與服務架構">
    <div className="kg-technology-caption"><span>THE KUANGUARD ECOSYSTEM</span><Blocks size={17} aria-hidden="true" /></div>
    <div className="kg-network">
      <svg className="kg-network-lines" viewBox="0 0 520 400" aria-hidden="true"><defs><linearGradient id="kg-line" x1="0" x2="1"><stop stopColor="#d6deea" /><stop offset=".5" stopColor="#668bec" /><stop offset="1" stopColor="#d6deea" /></linearGradient></defs><path d="M126 93 H218 Q260 93 260 135 V202 H405 M260 225 V306 H183" /><circle cx="260" cy="93" r="4" /><circle cx="405" cy="202" r="4" /><circle cx="183" cy="306" r="4" /></svg>
      <div className="kg-core-shadow" aria-hidden="true" /><div className="kg-core"><span>K</span><small>KUANGUARD</small></div>
      <Link className="kg-network-node kg-node-ordering" href="/products/ordering"><Store size={20} aria-hidden="true" /><span><small>PRODUCT</small><strong>商家 SaaS</strong></span><ArrowUpRight size={13} aria-hidden="true" /></Link>
      <Link className="kg-network-node kg-node-partner" href="/partners"><Network size={20} aria-hidden="true" /><span><small>PLATFORM</small><strong>夥伴協作</strong></span><ArrowUpRight size={13} aria-hidden="true" /></Link>
      <Link className="kg-network-node kg-node-security" href="/services"><ShieldCheck size={20} aria-hidden="true" /><span><small>SERVICE</small><strong>企業資安</strong></span><ArrowUpRight size={13} aria-hidden="true" /></Link>
    </div>
    <div className="kg-technology-foot"><span>不同專業，共同連接。</span><span>PRODUCTS / PLATFORMS / SERVICES</span></div>
  </div>;
}
function ProductVisual({ kind }: { kind: string }) {
  return <div className={`kg-product-visual kg-visual-${kind}`} aria-hidden="true">
    {kind === "ordering" ? <div className="kg-mini-window"><div className="kg-mini-top"><Store size={14} /><strong>商家工作空間</strong><span>營運概覽</span></div><div className="kg-mini-order"><div><small>顧客</small><strong>掃碼點餐</strong></div><ArrowRight size={15} /><div><small>門市</small><strong>確認出單</strong></div></div><div className="kg-mini-check"><Check size={12} /><span>餐點、備註與製作資訊，一目了然。</span></div></div>
      : kind === "partner" ? <div className="kg-mini-window"><div className="kg-mini-top"><Network size={14} /><strong>Partner Portal</strong><span>服務協作</span></div>{["客戶與專案", "團隊與授權", "品牌與交付"].map((label, i) => <div className="kg-mini-project" key={label}><span>0{i + 1}</span><strong>{label}</strong><div /></div>)}</div>
      : <div className="kg-mini-window"><div className="kg-mini-top"><ShieldCheck size={14} /><strong>企業安全</strong><span>服務流程</span></div><div className="kg-mini-security"><ShieldCheck size={32} strokeWidth={1.3} /><div><strong>從風險，到改善。</strong><span>檢測　/　覆核　/　交付</span></div></div><div className="kg-mini-check"><FileCheck2 size={12} /><span>保留證據，持續追蹤。</span></div></div>}
    <span className="kg-visual-label">功能流程示意</span>
  </div>;
}
function ProductCards() {
  return <div className="kg-product-grid">{products.map(product => <Link className="kg-product-card" href={product.href} key={product.id}>
    <ProductVisual kind={product.kind} /><div className="kg-product-copy"><div className="kg-product-category"><span>{product.category}</span><span>{product.id}</span></div><h3>{product.name}</h3><p>{product.description}</p><div className="kg-product-tags">{product.tags.map(tag => <span key={tag}>{tag}</span>)}</div><span className="kg-card-link">{product.action}<ArrowUpRight size={17} aria-hidden="true" /></span></div>
  </Link>)}</div>;
}
function AudienceRows() {
  return <div className="kg-audiences">{audiences.map(({ id, title, text, href, label, icon: Icon }) => <Link className="kg-audience-row" href={href} key={id}><span className="kg-row-number">{id}</span><div className="kg-audience-title"><Icon size={23} strokeWidth={1.5} aria-hidden="true" /><h3>{title}</h3></div><p>{text}</p><span className="kg-audience-link">{label}<ArrowUpRight size={17} aria-hidden="true" /></span></Link>)}</div>;
}
function Closing() {
  return <section className="kg-closing"><div className="kg-container"><div><Eyebrow>LET’S BUILD WHAT’S NEXT</Eyebrow><h2>你的下一個數位計畫，<br />從一次對話開始。</h2><p>告訴我們你的使用情境，一起找到合適的產品與服務。</p></div><Action href="/contact">與 KUANGUARD 聯繫</Action></div></section>;
}
export function CorporateHome() {
  return <div className="kg-site">
    <section className="kg-hero"><div className="kg-container kg-hero-grid"><div className="kg-hero-copy"><Eyebrow>DIGITAL TECHNOLOGY, REAL CONNECTIONS</Eyebrow><h1>數位科技，<br /><em>走進每一天的營運。</em></h1><p>從 SaaS 產品、企業資安到夥伴協作，<br className="kg-desktop-break" />KUANGUARD 讓資訊更有條理，讓團隊的下一步更清楚。</p><div className="kg-actions"><Action href="/products">探索產品與平台</Action><Action href="/contact" secondary>聊聊你的需求</Action></div><div className="kg-hero-signature"><span />科技的價值，來自每一次實際應用。</div></div><TechnologyVisual /></div></section>
    <div className="kg-focus-strip"><div className="kg-container"><span>讓不同的專業，找到共同的連結。</span><div><span><Blocks size={16} />數位產品</span><span><Network size={16} />平台協作</span><span><ShieldCheck size={16} />資訊安全</span></div></div></div>
    <section className="kg-section kg-container" id="products"><div className="kg-section-heading"><div><Eyebrow>PRODUCTS & PLATFORMS</Eyebrow><h2>各有專長，<br />為實際的工作而生。</h2></div><p>從一項合適的工具開始，<br />讓日常營運、專業服務與團隊協作逐步連接。</p></div><ProductCards /><div className="kg-section-foot"><span>產品功能與服務範圍，依各項目的介紹與開通條件提供。</span><Link href="/products">查看產品與平台<ArrowRight size={16} aria-hidden="true" /></Link></div></section>
    <section className="kg-solutions-section"><div className="kg-container kg-section"><div className="kg-section-heading"><div><Eyebrow>SOLUTIONS FOR YOUR BUSINESS</Eyebrow><h2>從你的使用情境出發。</h2></div><p>無論經營一間店，或服務一群客戶，<br />都能找到適合的數位起點。</p></div><AudienceRows /></div></section>
    <section className="kg-trust"><div className="kg-container kg-trust-grid"><div><Eyebrow>CONNECTED. WITH CONFIDENCE.</Eyebrow><h2>讓資訊流動，<br />也讓每一步值得信任。</h2><p>清楚的權限、可追蹤的流程與有依據的交付，<br />是數位工作可以持續運作的基礎。</p><Link href="/security" className="kg-trust-link">了解我們如何保護資料<ArrowUpRight size={17} aria-hidden="true" /></Link></div><div className="kg-trust-principles">{[[KeyRound, "資料各有邊界", "依企業、角色與專案授權，存取工作所需的資訊。"], [Workflow, "流程清楚可循", "讓客戶、團隊與服務夥伴掌握各自的下一步。"], [FileCheck2, "交付保留依據", "從檢測證據、覆核到報告，保留版本與服務紀錄。"]].map(([Icon, title, description]) => { const PrincipleIcon = Icon as typeof KeyRound; return <article key={String(title)}><PrincipleIcon size={22} strokeWidth={1.5} aria-hidden="true" /><div><h3>{String(title)}</h3><p>{String(description)}</p></div></article>; })}</div></div></section>
    <Closing />
  </div>;
}
export function CorporateProducts() {
  return <div className="kg-site"><section className="kg-page-intro kg-container"><Eyebrow>KUANGUARD / PRODUCTS & PLATFORMS</Eyebrow><h1>讓數位工具，<br /><em>成為工作的助力。</em></h1><p>KUANGUARD 旗下產品與服務，從商家營運到企業安全與夥伴協作。<br />選擇適合的起點，了解每一項產品的功能與導入方式。</p></section><section className="kg-container kg-catalog-section"><ProductCards /><p className="kg-catalog-note">點餐系統為 KUANGUARD 旗下商家 SaaS 產品；收費與功能狀態請見產品專頁。<br />企業資安由專業服務與核定交付流程提供，Partner 平台則支援合作夥伴管理與協作。</p></section><Closing /></div>;
}
export function CorporateSolutions() {
  return <div className="kg-site"><section className="kg-page-intro kg-container"><Eyebrow>KUANGUARD / SOLUTIONS</Eyebrow><h1>好的數位方案，<br /><em>從理解工作開始。</em></h1><p>先釐清你的使用情境，再選擇需要的產品、服務與協作方式。</p></section><section className="kg-container kg-catalog-section"><AudienceRows /><div className="kg-adoption"><Eyebrow>HOW WE GET STARTED</Eyebrow><h2>一步一步，把需求帶進實際工作。</h2><ol>{["了解使用情境", "確認產品與服務範圍", "安排導入與驗收", "持續服務與協作"].map((step, i) => <li key={step}><span>0{i + 1}</span>{step}</li>)}</ol></div></section><Closing /></div>;
}
