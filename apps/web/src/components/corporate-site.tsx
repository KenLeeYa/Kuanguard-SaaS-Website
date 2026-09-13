"use client";

import { useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { ArrowRight, ArrowUpRight, BookOpen, CarFront, ChevronRight, Handshake, HeartPulse, House, Menu, Network, Scissors, ShieldCheck, Shirt, Sparkles, Store, X } from "lucide-react";
import Link from "./guarded-link";
import { CommerceBrand, PartnersPage } from "./commerce-site";
import { LanguageSwitcher, Localized } from "./website-language";
import { splitLocale } from "@/lib/locales";
import { stallOrder } from "@/lib/product-links";
import { cooperationDomains, cooperationFaq, cooperationModes, cooperationSteps, introduction, ownProducts } from "@/lib/website-introduction";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <Localized><span className="kg-eyebrow">{children}</span></Localized>;
}
function Action({ href, children, secondary = false }: { href: string; children: React.ReactNode; secondary?: boolean }) {
  return <Localized><Link className={secondary ? "kg-button kg-button-secondary" : "kg-button"} href={href}>{children}<ArrowUpRight size={17} aria-hidden="true" /></Link></Localized>;
}
export function CorporateHeader() {
  const [open, setOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const path = "/" + splitLocale(usePathname()).path;
  const navigation = [["/products", "我們的系統"], ["/solutions", "合作領域"], ["/partners", "廠商合作"], ["/services", "企業資安"]];
  return <Localized><header className="kg-header" onKeyDown={event => { if (event.key === "Escape" && open) { setOpen(false); menuButton.current?.focus(); } }}>
    <div className="kg-container kg-header-inner">
      <CommerceBrand />
      <button ref={menuButton} className="kg-menu-button" aria-label={open ? "關閉主要選單" : "開啟主要選單"} aria-expanded={open} aria-controls="corporate-navigation" onClick={() => setOpen(!open)}>{open ? <X size={21} /> : <Menu size={21} />}</button>
      <nav id="corporate-navigation" className={open ? "is-open" : ""} aria-label="主要導覽" onClick={event => { if (event.target instanceof Element && event.target.closest("a")) setOpen(false); }}>
        {navigation.map(([href, label]) => <Link key={href} href={href} aria-current={path === href ? "page" : undefined}>{label}</Link>)}
        <LanguageSwitcher /><span className="kg-nav-actions"><Link href="/partner/login">合作夥伴登入<ArrowUpRight size={13} aria-hidden="true" /></Link><Action href="/contact">聯絡我們</Action></span>
      </nav>
    </div>
  </header></Localized>;
}
export function CorporateFooter() {
  return <Localized><footer className="kg-footer"><div className="kg-container">
    <div className="kg-footer-grid"><div className="kg-footer-brand"><CommerceBrand /><p>從數位產品出發，探索跨領域系統合作。</p></div>
      <div><strong>產品與服務</strong><Link href="/products/ordering">商家點餐系統</Link><Link href="/products#beauty">美業預約服務</Link><Link href="/products#studymesh">StudyMesh</Link><Link href="/services">企業資安服務</Link></div>
      <div><strong>探索 KUANGUARD</strong><Link href="/about">關於我們</Link><Link href="/solutions">合作領域</Link><Link href="/partners">廠商合作</Link><Link href="/contact">聯絡我們</Link><Link href="/security">資料安全</Link></div>
      <div><strong>服務入口</strong><Link href="/login">平台登入</Link><Link href="/partner/login">合作夥伴登入</Link><Link href="/merchant/apply">商家產品申請</Link></div>
    </div>
    <div className="kg-footer-bottom"><span>© {new Date().getFullYear()} KUANGUARD</span><LanguageSwitcher /><div><Link href="/privacy">隱私權政策</Link><Link href="/terms">服務條款</Link><Link href="/accessibility">網站使用與無障礙</Link></div></div>
  </div></footer></Localized>;
}
export function OrderingBreadcrumb({ path }: { path: string }) {
  return <Localized><nav className="kg-product-breadcrumb" aria-label="產品位置"><div className="commerce-container"><Link href="/">KUANGUARD 數位科技</Link><ChevronRight size={13} aria-hidden="true" /><Link href="/products">旗下產品</Link><ChevronRight size={13} aria-hidden="true" /><Link href="/products/ordering" aria-current={path === "products/ordering" ? "page" : undefined}>商家點餐系統</Link></div></nav></Localized>;
}

const productIcons = { ordering: Store, beauty: Scissors, studymesh: BookOpen };
const domainIcons = { food: Store, beauty: Scissors, clothing: Shirt, home: House, transport: CarFront, leisure: Sparkles, medical: HeartPulse, academic: BookOpen };
function ProductIndex() {
  return <Localized><aside className="kg-product-index" aria-labelledby="product-index-title">
    <p className="kg-eyebrow">KUANGUARD</p><h2 id="product-index-title">我們的數位產品</h2>
    {ownProducts.map(product => { const Icon = productIcons[product.id]; return <Link href={"/products#" + product.id} key={product.id}><Icon size={25} strokeWidth={1.5} aria-hidden="true" /><span><strong>{product.name}</strong><small>{product.status}</small></span><ArrowUpRight size={18} aria-hidden="true" /></Link>; })}
    <p>產品與合作規劃，各有清楚的開放狀態。</p>
  </aside></Localized>;
}
function ProductCards() {
  return <Localized><div className="kg-product-grid kg-owned-products">{ownProducts.map(product => { const Icon = productIcons[product.id]; return <article className="kg-product-card" id={product.id} key={product.id}>
    <div className="kg-owned-heading"><Icon size={30} strokeWidth={1.5} aria-hidden="true" /><span className="kg-platform-status">{product.status}</span></div>
    <div className="kg-product-copy"><p className="kg-product-category">{product.category}</p><h3>{product.name}</h3><p>{product.description}</p><p className="kg-product-note">{product.note}</p>
      <div className="kg-card-actions"><Link className="kg-card-link" href={product.href}>{product.action}<ArrowUpRight size={17} aria-hidden="true" /></Link>{product.id === "ordering" && <a className="kg-card-link" href={stallOrder.login}>商家登入<ArrowUpRight size={17} aria-hidden="true" /></a>}</div>
      {product.website && <a className="kg-official-site" href={product.website}>{new URL(product.website).hostname}<ArrowUpRight size={14} aria-hidden="true" /></a>}
    </div>
  </article>; })}</div></Localized>;
}
function ProductsSection() {
  return <Localized><section className="kg-section kg-container" id="products" aria-labelledby="products-title">
    <div className="kg-section-heading"><div><Eyebrow>自有產品方向</Eyebrow><h2 id="products-title">{introduction.productsTitle}</h2></div><p>{introduction.productsDescription}</p></div><ProductCards />
  </section></Localized>;
}
function ProfessionalServices() {
  return <Localized><section className="kg-container kg-professional" aria-labelledby="professional-title"><h2 id="professional-title">企業資安與夥伴協作</h2><div className="kg-professional-grid">
    <article><ShieldCheck size={25} aria-hidden="true" /><h3>企業資安服務</h3><p>從風險檢測到報告、改善與教育訓練，讓專業判斷成為可以追蹤的行動。</p><Link href="/services">了解資安服務<ArrowUpRight size={17} aria-hidden="true" /></Link></article>
    <article><Network size={25} aria-hidden="true" /><h3>合作夥伴平台</h3><p>合作平台規劃連接品牌、客戶與交付工作，目前尚未開放登入。</p><Link href="/partners#partner-platform">認識 Partner 平台<ArrowUpRight size={17} aria-hidden="true" /></Link><Link href="/partner/login">合作夥伴登入<ArrowUpRight size={17} aria-hidden="true" /></Link></article>
  </div></section></Localized>;
}
function DomainsSection() {
  return <Localized><section className="kg-solutions-section" id="domains" aria-labelledby="domains-title"><div className="kg-container kg-section">
    <div className="kg-section-heading"><div><Eyebrow>開放合作領域</Eyebrow><h2 id="domains-title">{introduction.domainsTitle}</h2></div><p>{introduction.domainsDescription}</p></div>
    <div className="kg-domain-grid">{cooperationDomains.map(domain => { const Icon = domainIcons[domain.id]; return <article key={domain.id}><Icon size={25} strokeWidth={1.5} aria-hidden="true" /><h3>{domain.title}</h3><p>{domain.description}</p></article>; })}</div>
    <p className="kg-direction-note">以上為合作方向，不代表已有合作廠商或已完成介接。</p>
  </div></section></Localized>;
}
function CooperationSection() {
  return <Localized><section className="kg-section kg-container" id="cooperation" aria-labelledby="cooperation-title">
    <div className="kg-section-heading"><div><Eyebrow>廠商合作</Eyebrow><h2 id="cooperation-title">{introduction.cooperationTitle}</h2></div><p>{introduction.cooperationDescription}</p></div>
    <div className="kg-cooperation-grid">{cooperationModes.map(([title, description], index) => <article key={title}><span className="kg-row-number">0{index + 1}</span><h3>{title}</h3><p>{description}</p></article>)}</div>
    <div className="kg-actions"><Action href="/contact?kind=partner">洽談合作</Action><Link className="kg-inline-link" href="/partners#partner-platform">認識 Partner 平台<ArrowRight size={17} aria-hidden="true" /></Link></div>
  </section></Localized>;
}
function VisionSection() {
  return <Localized><section className="kg-trust kg-cooperation-vision" id="vision" aria-labelledby="vision-title"><div className="kg-container kg-trust-grid">
    <div><span className="kg-platform-status">合作規劃中</span><h2 id="vision-title">{introduction.visionTitle}</h2><p>{introduction.visionDescription}</p></div>
    <ul>{introduction.visionPrinciples.map(principle => <li key={principle}>{principle}</li>)}</ul>
  </div></section></Localized>;
}
function ProcessSection() {
  return <Localized><section className="kg-section kg-container kg-cooperation-process" id="process" aria-labelledby="process-title"><Eyebrow>從交流到合作</Eyebrow><h2 id="process-title">合作如何開始</h2>
    <ol>{cooperationSteps.map(([title, description], index) => <li key={title}><span className="kg-row-number">0{index + 1}</span><h3>{title}</h3><p>{description}</p></li>)}</ol>
  </section></Localized>;
}
function FaqSection() {
  return <Localized><section className="kg-container kg-cooperation-faq" id="faq" aria-labelledby="faq-title"><div><Eyebrow>合作前，先了解</Eyebrow><h2 id="faq-title">合作常見問題</h2><p>從產品介紹開始，依實際需求確認合作範圍。</p></div><div>{cooperationFaq.map(([question, answer]) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</div></section></Localized>;
}
function Closing() {
  return <Localized><section className="kg-closing"><div className="kg-container"><div><Handshake size={27} aria-hidden="true" /><h2>聊聊您的系統與合作想法</h2><p>歡迎提供公司或系統名稱、服務領域、官網與合作想法。</p></div><Action href="/contact?kind=partner">洽談系統合作</Action></div></section></Localized>;
}
export function CorporateHome() {
  return <Localized><div className="kg-site kg-introduction">
    <section className="kg-hero"><div className="kg-container kg-hero-grid"><div className="kg-hero-copy"><Eyebrow>數位產品與系統合作</Eyebrow><h1>{introduction.headline[0]}<br /><em>{introduction.headline[1]}</em></h1><p>{introduction.description}</p><div className="kg-actions"><Action href="/#products">探索我們的系統</Action><Action href="/#cooperation" secondary>洽談系統合作</Action></div></div><ProductIndex /></div></section>
    <ProductsSection /><DomainsSection /><CooperationSection /><VisionSection /><ProcessSection /><FaqSection /><ProfessionalServices /><Closing />
  </div></Localized>;
}
export function CorporateProducts() {
  return <Localized><div className="kg-site kg-introduction"><section className="kg-page-intro kg-container"><Eyebrow>KUANGUARD</Eyebrow><h1>我們的數位產品</h1><p>{introduction.productsDescription}</p></section><section className="kg-container kg-catalog-section" aria-label="自有產品方向"><h2 className="sr-only">自有產品方向</h2><ProductCards /></section><ProfessionalServices /><Closing /></div></Localized>;
}
export function CorporateSolutions() {
  return <Localized><div className="kg-site kg-introduction"><section className="kg-page-intro kg-container"><Eyebrow>KUANGUARD</Eyebrow><h1>各領域合作方向</h1><p>從產品介紹與服務連結開始，歡迎各領域系統廠商一起探索合作。</p></section><DomainsSection /><CooperationSection /><Closing /></div></Localized>;
}
export function CorporatePartners() {
  return <Localized><div className="kg-site kg-introduction"><section className="kg-page-intro kg-container"><Eyebrow>KUANGUARD</Eyebrow><h1>讓專業系統，找到更多合作可能</h1><p>保留原有系統與服務關係，從一次交流開始。</p></section><CooperationSection /><VisionSection /><ProcessSection /><FaqSection /><section id="partner-platform" className="kg-existing-partner"><PartnersPage embedded /></section><Closing /></div></Localized>;
}
