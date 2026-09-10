"use client";

import Link from "./guarded-link";
import { useRouter } from "next/navigation";
import { useState, type ComponentType, type ReactNode } from "react";
import { AlertCircle, Bell, BookOpen, BriefcaseBusiness, Building2, CalendarDays, ChartNoAxesCombined, ClipboardCheck, CreditCard, FileCheck2, FileInput, FileText, FolderKanban, Gauge, HelpCircle, Layers3, LayoutDashboard, ListChecks, LockKeyhole, LogOut, Mail, Menu, Settings2, ShieldCheck, Unplug, Users, Wallet } from "lucide-react";
import { ApiError, confirmFormNavigation, dateOnly, dateTime, items, useMutation, useResource, useSession } from "@/lib/api";
import { serviceName } from "@/lib/catalog";
import { Badge, Brand, ButtonLink, Card, Empty, ErrorState, Loading, MutationStatus, Notice, PageHeading, Status } from "./ui";
import { CalendarPage, Campaigns, Dashboard, FindingDetail, findingColumns, ListPage, Organization, ProjectDetail, Projects, QuotesPage, RecipientGroups, reportColumns, SupportPage, TextAction, TrainingPage, WalletPage } from "./customer";
import { ImportsPage, IntegrationsPage, InternalOverview, InternalProjects, InternalQuotes, ReportJobsPage, ReviewPage, RetestsPage } from "./internal";
import { Certificate, LearnerCourse, LearnerHome } from "./learner";
import { PortfolioPage } from "./portfolio";
import { FinancePage } from "./operations-forms";
import { DeliveryReconciliation } from "./delivery-reconciliation";
import { NotificationsPage, Questionnaires, TicketsPage } from "./operations-workspace";
import { InternalChanges } from "./project-controls";
import { TrainingLicenses } from "./training-licenses";
import { CustomerDataPage, InternalLifecycle } from "./data-lifecycle";
import { LearnerManagement } from "./learner-management";
import { DispatchPage } from "./dispatch-page";
import { ProjectCostsPage } from "./project-execution";

type NavItem = { href: string; label: string; icon: ComponentType<{ size?: number }>; roles: string[]; group?: string; allRoles?: boolean };
export const customerNav: NavItem[] = [
  { href: "/dashboard", label: "企業工作台", icon: LayoutDashboard, roles: ["customer_contact"] },
  { href: "/projects", label: "我的專案", icon: FolderKanban, roles: ["customer_contact"] },
  { href: "/calendar", label: "服務日曆", icon: CalendarDays, roles: ["customer_contact"] },
  { href: "/findings", label: "檢測與改善", icon: ShieldCheck, roles: ["customer_contact"] },
  { href: "/reports", label: "正式報告", icon: FileCheck2, roles: ["customer_contact"] },
  { href: "/phishing/campaigns", label: "社交工程活動", icon: Mail, roles: ["campaign_manager"], group: "企業自助服務" },
  { href: "/phishing/groups", label: "受測群組", icon: Users, roles: ["campaign_manager"] },
  { href: "/phishing/report", label: "可疑郵件回報", icon: AlertCircle, roles: ["campaign_manager"] },
  { href: "/training", label: "教育訓練", icon: BookOpen, roles: ["training_manager"] },
  { href: "/wallet", label: "點數錢包", icon: Wallet, roles: ["billing_manager"] },
  { href: "/entitlements", label: "服務額度", icon: Layers3, roles: ["customer_contact"], group: "企業管理" },
  { href: "/quotes", label: "報價與確認", icon: FileText, roles: ["customer_contact"] },
  { href: "/contracts", label: "合約紀錄", icon: BriefcaseBusiness, roles: ["customer_contact"] },
  { href: "/orders", label: "購點訂單", icon: CreditCard, roles: ["billing_manager"] },
  { href: "/organization", label: "企業組織", icon: Building2, roles: ["customer_admin"] },
  { href: "/organization/learners", label: "學員與部門", icon: Users, roles: ["customer_admin", "training_manager"] },
  { href: "/organization/data", label: "資料與退場申請", icon: FileText, roles: ["customer_admin", "customer_contact", "campaign_manager", "training_manager", "billing_manager"] },
  { href: "/questionnaires", label: "資安問卷與證據", icon: ClipboardCheck, roles: ["customer_admin"] },
  { href: "/notifications", label: "我的通知", icon: Bell, roles: ["customer_contact", "customer_admin", "campaign_manager", "training_manager", "billing_manager"] },
  { href: "/support", label: "支援與工單", icon: HelpCircle, roles: ["customer_contact", "customer_admin", "campaign_manager", "training_manager", "billing_manager"] },
];
export const internalNav: NavItem[] = [
  { href: "/admin/overview", label: "營運總覽", icon: LayoutDashboard, roles: ["pm", "engineer", "reviewer", "finance", "platform_admin"] },
  { href: "/admin/projects", label: "專案與工作包", icon: FolderKanban, roles: ["pm", "engineer", "reviewer"] },
  { href: "/admin/crm", label: "詢價需求", icon: Building2, roles: ["pm"] },
  { href: "/admin/quotes", label: "報價管理", icon: FileText, roles: ["pm"] },
  { href: "/admin/dispatch", label: "人員與派工", icon: CalendarDays, roles: ["pm"] },
  { href: "/admin/changes", label: "範圍與時程變更", icon: FileText, roles: ["pm"] },
  { href: "/admin/imports", label: "資料匯入", icon: FileInput, roles: ["engineer"], group: "技術處理與交付" },
  { href: "/admin/review", label: "技術覆核", icon: ClipboardCheck, roles: ["reviewer"] },
  { href: "/admin/shc", label: "系統健診結果", icon: ListChecks, roles: ["engineer", "reviewer"] },
  { href: "/admin/pt", label: "滲透測試結果", icon: ShieldCheck, roles: ["engineer", "reviewer"] },
  { href: "/admin/source", label: "源碼檢測結果", icon: Layers3, roles: ["engineer", "reviewer"] },
  { href: "/admin/retests", label: "複測申請與驗證", icon: ShieldCheck, roles: ["pm", "engineer", "reviewer"] },
  { href: "/admin/reports", label: "報告產製與發布", icon: FileCheck2, roles: ["engineer", "reviewer"] },
  { href: "/admin/billing", label: "財務對帳", icon: CreditCard, roles: ["finance"], group: "營運管理" },
  { href: "/admin/billing/project-costs", label: "專案工時與成本", icon: Wallet, roles: ["pm", "finance"] },
  { href: "/admin/phishing-operations", label: "郵件接受狀態對帳", icon: Mail, roles: ["finance"] },
  { href: "/admin/questionnaires", label: "問卷證據覆核", icon: ClipboardCheck, roles: ["reviewer"] },
  { href: "/admin/training", label: "教育訓練席次", icon: BookOpen, roles: ["pm"] },
  { href: "/admin/tickets", label: "企業支援工單", icon: HelpCircle, roles: ["pm"] },
  { href: "/admin/administration/lifecycle", label: "企業退場審核", icon: Settings2, roles: ["pm", "finance"], allRoles: true },
  { href: "/admin/notifications", label: "我的通知", icon: Bell, roles: ["pm", "engineer", "reviewer", "finance", "platform_admin", "portfolio_owner"] },
  { href: "/admin/integrations", label: "整合服務", icon: Unplug, roles: ["platform_admin", "pm"] },
  { href: "/admin/audit", label: "稽核紀錄", icon: LockKeyhole, roles: ["platform_admin", "pm", "finance"] },
  { href: "/admin/portfolio", label: "公司總管理", icon: ChartNoAxesCombined, roles: ["portfolio_owner"], group: "公司總覽" },
  ...[["products", "產品健康", Gauge], ["finance", "財務摘要", CreditCard], ["tasks", "跨產品待辦", ListChecks], ["operations", "產品營運", Layers3], ["costs", "成本與預算", Wallet], ["integrations", "彙總資料來源", Settings2]].map(([path, label, icon]) => ({ href: `/admin/portfolio/${path}`, label: String(label), icon: icon as NavItem["icon"], roles: ["portfolio_owner"] })),
];
const learnerNav: NavItem[] = [{ href: "/learn", label: "我的學習", icon: BookOpen, roles: ["learner"] }, { href: "/learn/notifications", label: "我的通知", icon: Bell, roles: ["learner"] }];
const allows = (roles: string[], required: string[]) => required.some(r => roles.includes(r));
const allowsNav = (roles: string[], entry: NavItem) => entry.allRoles ? entry.roles.every(role => roles.includes(role)) : allows(roles, entry.roles);
function ProductionLogin() {
  const provider = useResource("/auth/providers");
  if (provider.loading) return <Loading />;
  if (provider.error) return <ErrorState error={provider.error} retry={provider.reload} />;
  const enabled = items(provider.data).filter(p => typeof p.url === "string" && p.url.startsWith("/api/auth/") && !p.url.includes("//"));
  return enabled.length ? <div className="form-stack section-gap">{enabled.map(p => <a className="button" key={p.id} href={p.url}>{p.label}</a>)}</div> : <Notice>正式企業身份驗證尚未啟用。請由管理者完成 IdP 設定及企業授權後登入。<br /><Link className="text-link" href="/request-quote">聯絡服務團隊</Link></Notice>;
}
export function homeFor(roles: string[]) { if (roles.includes("portfolio_owner")) return "/admin/portfolio"; if (roles.some(r => ["pm", "engineer", "reviewer", "finance", "platform_admin"].includes(r))) return "/admin/overview"; if (roles.includes("customer_contact")) return "/dashboard"; if (roles.includes("campaign_manager")) return "/phishing/campaigns"; if (roles.includes("training_manager")) return "/training"; if (roles.includes("billing_manager")) return "/wallet"; if (roles.includes("customer_admin")) return "/organization"; return "/learn"; }
export function LoginPage() { const profiles = useResource("/auth/dev/profiles"); const { session, loading, refresh } = useSession(); const action = useMutation(); const router = useRouter(); return <section className="login-page"><div className="login-card"><Brand /><h1>登入您的工作空間</h1><p>企業工作、內部交付與個人學習，依實際身份授權進入。</p>{loading ? <Loading /> : session ? <div className="login-current"><Notice>目前登入：{session.user.name} · {session.tenant.name}</Notice><ButtonLink href={homeFor(session.roles)}>前往我的工作空間</ButtonLink><button className="button button-secondary section-gap" disabled={action.pending} onClick={async () => { if (await action.mutate("/auth/logout")) await refresh(); }}>登出並切換身份</button></div> : profiles.loading ? <Loading /> : profiles.error ? <ProductionLogin /> : <><Notice>本機開發登入 · 僅在後端開發模式開啟。下列身份使用合成資料，正式環境不提供角色切換。</Notice><div className="profile-grid">{items(profiles.data).map(p => <button className="profile-button" disabled={action.pending} key={p.key} onClick={async () => { const result = await action.mutate("/auth/dev/login", { profile_key: p.key }); if (result) { await refresh(); router.push(homeFor(p.roles)); } }}><strong>{p.label}</strong><small>{p.roles.join(" · ")}</small></button>)}</div></>}<MutationStatus action={{ ...action, result: null }} /><p className="form-help">登入不代表取得所有企業資料；每個專案與功能仍由後端重新授權。</p></div></section>; }
export function WorkspacePage({ path }: { path: string }) { const { session, loading, error, refresh } = useSession(); const [navOpen, setNavOpen] = useState(false); const logout = useMutation(); const router = useRouter(); const internal = path.startsWith("admin"); const learner = path.startsWith("learn"); const fullPath = path === "assets" ? "/findings" : `/${path}`; const nav = internal ? internalNav : learner ? learnerNav : customerNav;
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} retry={refresh} />;
  if (!session) return <section className="login-page"><Card><div className="state-box"><LockKeyhole size={30} /><strong>請先登入您的工作空間</strong><span>資料需經身份與企業權限確認後才能載入。</span><ButtonLink href="/login">前往登入</ButtonLink></div></Card></section>;
  const bestMatch = [...nav].sort((a, b) => b.href.length - a.href.length).find(n => fullPath === n.href || fullPath.startsWith(`${n.href}/`));
  const permitted = bestMatch ? allowsNav(session.roles, bestMatch) : path === "onboarding" ? allows(session.roles, ["customer_admin"]) : false;
  const visibleNav = nav.filter(n => allowsNav(session.roles, n));
  return <div className="workspace">{navOpen && <button className="sidebar-overlay" aria-label="關閉側欄" onClick={() => setNavOpen(false)} />}<aside className={`sidebar ${navOpen ? "is-open" : ""}`}><Brand light /><p className="sidebar-caption">{internal ? "INTERNAL WORKSPACE" : learner ? "MY LEARNING" : "CUSTOMER WORKSPACE"}</p><nav className="side-nav" aria-label="工作空間導覽">{visibleNav.map(n => { const Icon = n.icon; const active = bestMatch?.href === n.href; return <div key={n.href}>{n.group && <div className="nav-group">{n.group}</div>}<Link className={active ? "active" : ""} href={n.href} aria-current={active ? "page" : undefined} onClick={() => setNavOpen(false)}><Icon size={17} />{n.label}</Link></div>; })}</nav><div className="sidebar-bottom"><ShieldCheck size={21} /><div><strong>您的資料，依權限守護。</strong>租戶隔離 · 操作留存</div></div></aside><div className="workspace-main"><header className="workspace-topbar"><div className="workspace-topbar-left"><button className="icon-button mobile-sidebar-toggle" aria-label="開啟工作選單" aria-expanded={navOpen} onClick={() => setNavOpen(!navOpen)}><Menu size={18} /></button><strong>{internal ? "內部作業" : learner ? "個人學習" : "企業工作空間"}</strong><span>/</span><span>{bestMatch?.label || "工作台"}</span></div><div className="workspace-topbar-right"><Link className="icon-button" aria-label="我的通知" href={internal ? "/admin/notifications" : learner ? "/learn/notifications" : "/notifications"}><Bell size={17} /></Link><span className="tenant-label"><Building2 size={14} />{session.tenant.name}</span><div className="user-meta"><div className="user-avatar">{session.user.name.slice(0, 1)}</div><span>{session.user.name}</span></div><button className="logout-button" disabled={logout.pending} onClick={async () => { if (!confirmFormNavigation()) return; if (await logout.mutate("/auth/logout")) { await refresh(); router.push("/login"); } }}><LogOut size={13} />登出</button></div></header>{session.development && <div className="development-banner"><AlertCircle size={13} /><span>本機開發環境 · 合成資料 · 正式寄送、付款與外部服務尚未啟用</span></div>}<main id="main-content" className="workspace-content">{permitted ? <WorkspaceContent path={path} /> : <Card><ErrorState error={new ApiError(403, "FORBIDDEN", "目前角色未獲授權使用此功能。請返回您的工作空間。") } /><div className="success-panel"><ButtonLink href={homeFor(session.roles)}>返回我的工作空間</ButtonLink></div></Card>}<footer className="workspace-footer"><span>KUANGUARD · 企業資安服務平台</span><span>時間顯示：Asia/Taipei · 權限依企業與角色</span></footer></main></div></div>;
}
function WorkspaceContent({ path }: { path: string }) {
  if (path === "dashboard") return <Dashboard />;
  if (path === "projects") return <Projects />;
  if (path.startsWith("projects/")) return <ProjectDetail id={path.split("/")[1]} initialTab={path.endsWith("/changes") ? "變更申請" : undefined} />;
  if (path === "calendar") return <CalendarPage />;
  if (path === "findings" || path === "assets") return <ListPage title="檢測結果與改善" description="僅顯示已發布版本。未知或未檢測範圍不表示安全，修補回覆仍需技術驗證。" endpoint="/customer/findings" columns={findingColumns} />;
  if (path.startsWith("findings/")) return <FindingDetail id={path.split("/")[1]} />;
  if (path === "reports") return <ListPage title="正式報告" description="核定資料快照生成的正式版本；每次下載重新確認授權並留下紀錄。" endpoint="/customer/reports" columns={reportColumns} />;
  if (path === "wallet") return <WalletPage />;
  if (path === "phishing/groups") return <RecipientGroups />;
  if (path === "phishing/report") return <><PageHeading title="可疑郵件回報" description="描述必要的郵件資訊與您已做的操作；請勿提供密碼或敏感附件。" /><TextAction title="新增文字回報" label="郵件時間、主旨與已做操作" endpoint="/customer/suspicious-mail-reports" field="description" /></>;
  if (path.startsWith("phishing")) return <Campaigns id={path.split("/")[2]} />;
  if (path.startsWith("training")) return <TrainingPage />;
  if (path === "support") return <SupportPage />;
  if (path.startsWith("support/")) return <TicketsPage id={path.split("/")[1]} />;
  if (path === "questionnaires" || path.startsWith("questionnaires/")) return <Questionnaires id={path.split("/")[1]} />;
  if (["notifications", "learn/notifications", "admin/notifications"].includes(path)) return <NotificationsPage />;
  if (path === "quotes") return <QuotesPage />;
  if (path === "organization") return <Organization />;
  if (path === "organization/data") return <CustomerDataPage />;
  if (path === "organization/learners") return <LearnerManagement />;
  if (path === "entitlements") return <ListPage title="檢測與顧問服務額度" description="合約檢測次數與顧問時數獨立記帳，不與企業點數混加。" endpoint="/customer/entitlements" columns={[{ key: "service_code", title: "服務", render: r => serviceName(r.service_code) }, { key: "quantity", title: "核定額度" }, { key: "available", title: "可用額度" }, { key: "reserved", title: "已預留", render: r => r.reserved ?? "依帳本" }, { key: "consumed", title: "已履約耗用", render: r => r.consumed ?? "依帳本" }, { key: "expires_at", title: "期限", render: r => dateOnly(r.expires_at) }]} />;
  if (["contracts", "orders"].includes(path)) return <ListPage title={path === "contracts" ? "合約紀錄" : "購點訂單"} description="合約、支付與發票狀態分開追蹤，依後端核對結果顯示。" endpoint={`/customer/${path}`} columns={[{ key: "title", title: "紀錄", render: r => r.title || r.id }, { key: "status", title: "狀態", render: r => <Status value={r.status} /> }, { key: "amount_minor", title: "金額（TWD）", render: r => r.amount_minor !== undefined ? (Number(r.amount_minor) / 100).toLocaleString() : "依合約" }, { key: "points", title: "點數", render: r => r.points ?? "不適用" }, { key: "created_at", title: "建立時間", render: r => dateTime(r.created_at) }]} />;
  if (path === "onboarding") return <><PageHeading title="企業開通" description="企業身份與管理權驗證完成後，便可獨立使用自助服務。" /><Card title="目前企業已由開發管理流程建立"><Notice>正式企業認領與邀請需接入核定 IdP。開發環境已建立兩企業驗證隔離；不因相同 Email 網域自動共享。</Notice><div className="actions"><ButtonLink href="/wallet">查看點數與購點</ButtonLink><ButtonLink href="/training" secondary>前往派課</ButtonLink></div></Card></>;
  if (path === "learn" || path === "learn/courses") return <LearnerHome />;
  if (path.startsWith("learn/courses/")) return <LearnerCourse id={path.split("/")[2]} />;
  if (path.startsWith("learn/certificates/")) return <Certificate id={path.split("/")[2]} />;
  if (path.startsWith("admin/portfolio")) return <PortfolioPage section={path.split("/")[2]} />;
  if (path === "admin/overview") return <InternalOverview />;
  if (path.startsWith("admin/projects")) return <InternalProjects id={path.split("/")[2]} />;
  if (path === "admin/imports") return <ImportsPage />;
  if (path === "admin/review") return <ReviewPage />;
  if (["admin/shc", "admin/pt", "admin/source"].includes(path)) return <ReviewPage service={{ "admin/shc": "SHC", "admin/pt": "PT", "admin/source": "SOURCE" }[path]} />;
  if (path === "admin/retests") return <RetestsPage />;
  if (path === "admin/reports") return <ReportJobsPage />;
  if (path === "admin/quotes") return <InternalQuotes />;
  if (path === "admin/changes") return <InternalChanges />;
  if (path === "admin/training") return <TrainingLicenses internal />;
  if (path === "admin/administration/lifecycle") return <InternalLifecycle />;
  if (path === "admin/integrations") return <IntegrationsPage />;
  if (path === "admin/crm") return <ListPage title="詢價需求" description="官網表單送入的實際需求紀錄，供 PM 評估與建立報價。" endpoint="/internal/leads" columns={[{ key: "company", title: "公司" }, { key: "contact_name", title: "窗口" }, { key: "email", title: "聯絡信箱" }, { key: "services", title: "服務", render: r => (r.services || []).map(serviceName).join("、") }, { key: "scope", title: "需求範圍", render: r => <p>{r.scope}</p> }, { key: "status", title: "狀態", render: r => <Status value={r.status} /> }]} />;
  if (path === "admin/dispatch") return <DispatchPage />;
  if (path === "admin/billing") return <FinancePage />;
  if (path === "admin/billing/project-costs") return <ProjectCostsPage />;
  if (path === "admin/phishing-operations") return <DeliveryReconciliation />;
  if (path === "admin/questionnaires" || path.startsWith("admin/questionnaires/")) return <Questionnaires id={path.split("/")[2]} internal />;
  if (path === "admin/tickets" || path.startsWith("admin/tickets/")) return <TicketsPage id={path.split("/")[2]} internal />;
  if (path === "admin/audit") return <ListPage title="稽核紀錄" description="記錄真實操作者、角色與操作時間；同一人兼任時保留同一 actor。" endpoint="/internal/audit" columns={[{ key: "created_at", title: "時間（Asia/Taipei）", render: r => dateTime(r.created_at) }, { key: "action", title: "行為" }, { key: "actor_id", title: "操作者" }, { key: "resource_id", title: "資源" }, { key: "trace_id", title: "追查編號" }]} />;
  return <Empty title="此頁面尚未開放">請使用側邊選單前往目前角色可用的功能。</Empty>;
}
