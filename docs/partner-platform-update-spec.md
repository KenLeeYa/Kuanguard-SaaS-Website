# Kuanguard 官網與 SaaS 平台重新定位 — Codex 增量更新 Prompt

## 0. 執行模式與最高原則

你正在既有 Kuanguard 專案上進行「增量更新」，不是重建專案。

請先完整掃描目前 repository、frontend、backend、database schema、authentication、tenant、billing、partner、security SaaS、ordering SaaS、deployment、Cloudflare、environment variables、CI/CD 與現有測試，再進行修改。

### 強制要求

1. 不得刪除、覆蓋或破壞目前已可運作的功能。
2. 不得重建整個專案或更換既有核心 framework，除非發現明確安全問題或相容性問題。
3. 所有變更必須採 migration / incremental refactor。
4. 既有企業資安 SaaS 功能必須保留。
5. 既有點餐 SaaS / Stallorder / Ordering Platform 功能必須保留。
6. 官網品牌定位改變，不代表移除資安 SaaS。
7. 資安 SaaS 從「Kuanguard 主官網核心服務」改為「合作夥伴 / Partner Portal 後方服務」。
8. Kuanguard 主官網未來以 SaaS Platform / 商家數位營運平台為核心。
9. Partner Portal 必須支援三傑科技，但架構不得寫死 Megaprotek，必須可支援未來 N 家 Partner。
10. 執行所有必要 lint、typecheck、unit test、integration test、build test。
11. 若目前系統已有同等功能，優先 reuse / refactor，不得建立重複模組。
12. 所有 secrets 必須由 environment variables 或 secret manager 管理，禁止 hard-code。
13. 所有 schema changes 必須附 migration。
14. 必須維持 backward compatibility。
15. 將所有變更記錄至 CHANGELOG / implementation report。

---

# 1. Kuanguard 新品牌定位

將：

`https://kuanguard.com`

重新定位為：

> Kuanguard SaaS Platform  
> 為商家提供點餐、營運、會員、支付、訂位、外送整合與數位經營的一站式 SaaS 平台。

Kuanguard 不再於首頁以「企業資安服務公司」為主要對外定位。

企業資安 SaaS 不刪除，而是改成：

> Partner / Enterprise Service Platform

由合作夥伴入口進入。

---

# 2. 建議的品牌架構

整體品牌關係：

```text
Kuanguard
│
├─ SaaS Commerce / Ordering Platform
│  ├─ 線上點餐
│  ├─ QR Code 點餐
│  ├─ 訂位
│  ├─ POS / 出單
│  ├─ 外送平台整合
│  ├─ 支付
│  ├─ 會員 CRM
│  ├─ 優惠與行銷
│  ├─ 商家營運
│  ├─ 多分店
│  └─ 後台管理
│
└─ Partner Platform
   ├─ 資安服務合作夥伴
   ├─ Partner Tenant
   ├─ VA
   ├─ WVA
   ├─ PT
   ├─ SHC
   ├─ Social Engineering
   ├─ Security Training
   ├─ Project Management
   ├─ Reports
   ├─ Credits
   └─ Enterprise Customer Portal
```

---

# 3. Domain Architecture

規劃：

```text
kuanguard.com
│
├─ www.kuanguard.com
│  Kuanguard SaaS 官網
│
├─ app.kuanguard.com
│  商家 SaaS 登入 / Merchant Portal
│
├─ admin.kuanguard.com
│  Kuanguard Super Admin
│
├─ partner.kuanguard.com
│  合作夥伴統一入口
│
├─ api.kuanguard.com
│  Backend API
│
├─ auth.kuanguard.com
│  Central Authentication
│
├─ docs.kuanguard.com
│  文件 / API / Partner Docs
│
└─ status.kuanguard.com
   Service Status
```

Partner Custom Domains：

```text
portal.megaprotek.com.tw
        │
        ▼
Kuanguard Partner Platform
        │
        ▼
Megaprotek Tenant
```

未來：

```text
portal.partner-b.com
portal.partner-c.com
```

都走相同架構。

禁止為每家 Partner 建立獨立 codebase。

---

# 4. Kuanguard 首頁重新設計

將主首頁改成商家 SaaS Landing Page。

## Hero

主標題建議：

> 一套平台，完成商家的數位營運

副標：

> 從 QR Code 點餐、線上訂位、付款、會員、出單到外送整合，Kuanguard 讓商家用更簡單的方式管理每一筆生意。

CTA：

- 免費開始
- 申請商家
- 查看功能
- 商家登入

右上角：

- 功能
- 解決方案
- 收費方式
- 合作夥伴
- 登入
- 免費開始

---

# 5. 首頁核心功能區

建立 SaaS Product Feature Grid：

### 線上點餐
- 商家專屬點餐頁
- QR Code 掃碼點餐
- 桌號
- 外帶
- 預約取餐
- 即時菜單
- 商品售罄
- 加料 / 規格

### 訂位
- 線上訂位
- 人數
- 時段
- 店內桌位
- 訂位管理
- 通知

### POS / 出單
- 訂單集中管理
- iPad / Tablet
- Star webPRNT
- 廚房列印
- 錢櫃
- 訂單狀態

### 支付
預留並呈現：

- LINE Pay
- Taiwan Pay
- 全支付
- 街口支付
- 信用卡
- Apple Pay / Google Pay（架構預留）

未啟用的支付方式不得假裝正式可使用。

### 外送整合
- foodpanda
- Uber Eats
- Future Delivery Connectors

必須區分：

`available`
`beta`
`planned`

不得在尚未完成正式 API 合作前誤導使用者。

### 會員 CRM
- 顧客資料
- 消費紀錄
- 回購分析
- 優惠券
- 點數
- 會員分級
- 行銷活動

### 多分店
- 店家
- 品牌
- 分店
- 多門市
- 分店菜單
- 分店營收
- 權限

### 營運分析
Dashboard：

- 今日營收
- 訂單數
- 客單價
- 熱門商品
- 時段分析
- 回購率
- 支付方式
- 通路占比

---

# 6. 收費模式

目前 Kuanguard Ordering Platform 核心商業模式：

> 不月租、不買斷，每筆成功訂單收取 NT$1 平台服務費。

前端必須清楚呈現，但需建立 configuration，不得 hard-code。

建立：

```text
BillingPlan
PlanVersion
PricingRule
UsageLedger
BillingCycle
BillingAdjustment
Invoice
CreditNote
```

成功訂單定義必須集中在 billing domain。

至少處理：

- completed order
- cancelled order
- refunded order
- partially refunded
- duplicate webhook
- test order
- manual order
- third-party order

建立 idempotency。

費率必須可後台調整。

例如：

```text
per_order_fee = 1 TWD
```

未來可以變更：

```text
monthly_cap
minimum_fee
partner_fee
merchant_specific_fee
promotion
```

---

# 7. Kuanguard 官網頁面 IA

建立 / 重構：

```text
/
├─ /features
├─ /solutions
│  ├─ /restaurant
│  ├─ /beverage
│  ├─ /food-stall
│  ├─ /retail
│  └─ /beauty
├─ /pricing
├─ /partners
├─ /about
├─ /contact
├─ /login
├─ /merchant/apply
├─ /partner/login
├─ /privacy
├─ /terms
└─ /security
```

SEO metadata、OpenGraph、canonical、structured data 一併補齊。

---

# 8. 原企業資安平台重新定位

原本 Kuanguard 官網企業資安服務相關 landing pages：

不要刪除資安 SaaS Backend。

改成 Partner 服務。

主官網只保留簡潔入口：

> 合作夥伴平台

說明：

> Kuanguard 提供合作夥伴專屬 SaaS Infrastructure，可支援企業服務、專案、客戶、報告與授權管理。

主官網不再直接把：

- VA
- WVA
- PT
- SHC
- 社交工程

當作 Kuanguard 對一般市場直接販售的主要首頁服務。

它們由 Partner Portal 提供。

---

# 9. Partner Portal

統一入口：

`https://partner.kuanguard.com`

登入後依使用者所屬 Partner Tenant 進入。

Partner 類型：

```text
SECURITY_SERVICE_PROVIDER
RESELLER
MSP
MSSP
CONSULTANT
TECHNOLOGY_PARTNER
REFERRAL_PARTNER
```

第一個正式 Partner：

```text
Megaprotek / 三傑科技
```

但不得 hard-code。

---

# 10. 三傑科技整合

三傑官方網站：

`https://www.megaprotek.com.tw`

新增 CTA：

> 客戶專區  
> 資安管理平台

連至：

`https://portal.megaprotek.com.tw`

或：

`https://partner.kuanguard.com/login?tenant=megaprotek`

正式 production 建議優先 Custom Domain：

`https://portal.megaprotek.com.tw`

---

# 11. 三傑 White Label

當 Host 是：

```text
portal.megaprotek.com.tw
```

讀取：

```text
tenant_domains
```

取得 tenant。

例如：

```text
organization:
  name: 三傑科技
  slug: megaprotek
  type: SECURITY_SERVICE_PROVIDER

domain:
  portal.megaprotek.com.tw

branding:
  logo
  favicon
  primary brand configuration
  company_name
  support_contact
```

UI：

> 三傑科技 資安管理平台  
> Powered by Kuanguard

不得讓三傑客戶誤以為已離開三傑服務體系。

---

# 12. Partner Dashboard

建立：

```text
/partner/dashboard
```

Dashboard：

- 客戶總數
- 進行中專案
- 即將開始專案
- 即將到期專案
- VA
- WVA
- PT
- SHC
- 社交工程
- 教育訓練
- 未完成修補
- 高風險弱點
- 點數餘額
- 使用量
- 最近報告
- 待處理事項
- 系統通知

---

# 13. Security Service Modules

必須保留並接入 Partner Tenant：

```text
VA
WVA
SHC
PT
Social Engineering
Security Awareness Training
```

檢測資料原則：

後端工程師到場或遠端執行檢測，完成後：

- 上傳掃描資料
- 上傳 Nessus
- 上傳 CSV
- 上傳 AppScan
- 上傳相關原始資料
- 建立 Project
- 建立 Finding
- 建立 Report
- 提供 Customer Portal

禁止把平台設計成未經授權的自動攻擊平台。

---

# 14. Partner Project Management

建立：

```text
customers
contracts
projects
project_services
project_members
project_milestones
project_schedules
project_documents
project_deliverables
project_findings
project_reports
project_notes
project_activity_logs
```

Service Types：

```text
VA
WVA
PT
SHC
SOCIAL_ENGINEERING
TRAINING
CONSULTING
OTHER
```

狀態：

```text
LEAD
QUOTED
SIGNED
SCHEDULED
IN_PROGRESS
RETEST
REPORTING
DELIVERED
CLOSED
CANCELLED
```

---

# 15. Partner / Customer Ownership

加入：

```text
customer_source
partner_id
organization_id
```

來源：

```text
DIRECT
PARTNER
RESELLER
REFERRAL
IMPORT
```

Customer 必須能追蹤：

- originating_partner
- owning_partner
- account_manager
- contract_owner
- service_provider

確保未來：

- 分潤
- 續約
- 客戶歸屬
- 業務績效
- Partner Commission

有完整基礎。

---

# 16. Multi-Tenant

Partner Portal 與 Merchant SaaS 都必須真正 Multi-Tenant。

不要複製 database。

核心：

```text
organizations
organization_members
organization_roles
tenant_domains
tenant_branding
tenant_settings
```

所有 tenant-owned entities 必須具：

```text
organization_id
```

或既有一致 tenant key。

所有 database access 必須 enforce tenant isolation。

如使用 PostgreSQL / Supabase，評估 Row Level Security。

禁止只靠 frontend 隱藏資料。

---

# 17. Unified Identity / Authentication

集中：

`auth.kuanguard.com`

支援：

- Google OAuth
- LINE Login
- Apple Sign In
- Microsoft Entra ID
- OIDC
- SAML 2.0（Enterprise / Partner）

Account 可同時具有：

```text
MERCHANT_OWNER
MERCHANT_STAFF
KUANGUARD_ADMIN
PARTNER_ADMIN
PARTNER_ENGINEER
PARTNER_SALES
PARTNER_FINANCE
CUSTOMER_ADMIN
CUSTOMER_USER
```

採 RBAC + tenant scope。

Partner User 不得存取其他 Partner Tenant。

---

# 18. 登入頁重新設計

`https://kuanguard.com/login`

改成 Unified Login Router。

呈現：

```text
Kuanguard

請選擇您的服務

[商家登入]
管理點餐、訂位、訂單與營運

[合作夥伴登入]
Partner / Enterprise Service Platform

[平台管理員]
Kuanguard Administration
```

登入後依角色自動導向。

---

# 19. Login Routing

例如：

```text
MERCHANT_OWNER
→ app.kuanguard.com

PARTNER_ADMIN
→ partner.kuanguard.com

KUANGUARD_ADMIN
→ admin.kuanguard.com
```

Custom Domain：

```text
portal.megaprotek.com.tw
```

登入完成後必須回到：

```text
portal.megaprotek.com.tw
```

不可跳到錯誤 tenant。

---

# 20. Central OAuth Callback

避免每家 Custom Domain 都建立一整套 OAuth callback。

建議：

```text
auth.kuanguard.com/oauth/callback
```

流程：

```text
Custom Domain
→ auth.kuanguard.com
→ OAuth Provider
→ auth.kuanguard.com/oauth/callback
→ validate state
→ validate tenant
→ issue session
→ redirect back to tenant domain
```

必須防：

- open redirect
- session fixation
- CSRF
- OAuth state replay
- tenant swapping

---

# 21. Custom Domain

建立：

```text
tenant_domains
```

至少：

```text
id
organization_id
domain
status
verification_token
verified_at
tls_status
is_primary
created_at
updated_at
```

狀態：

```text
PENDING
VERIFYING
ACTIVE
FAILED
DISABLED
```

加入 domain ownership verification。

---

# 22. Cloudflare

Kuanguard：

```text
kuanguard.com
app.kuanguard.com
partner.kuanguard.com
admin.kuanguard.com
api.kuanguard.com
auth.kuanguard.com
```

配置：

- DNS
- Proxy
- TLS
- HSTS
- WAF
- DDoS
- Rate Limiting
- Bot Protection
- Security Headers

Partner：

```text
portal.megaprotek.com.tw
CNAME
→ tenant/custom-domain endpoint
```

Cloudflare 設定必須文件化。

若 Codex 無法直接操作 Cloudflare：

建立：

`docs/CLOUDFLARE_SETUP.md`

列出使用者需手動完成的步驟。

不要阻斷其餘開發。

---

# 23. Security Headers

至少：

```text
Strict-Transport-Security
Content-Security-Policy
X-Content-Type-Options
Referrer-Policy
Permissions-Policy
```

評估：

```text
frame-ancestors
```

禁止不必要 iframe embedding。

---

# 24. Cookie / Session

Custom Domain 必須重新檢查：

- Secure
- HttpOnly
- SameSite
- Domain
- Path
- Session rotation
- Refresh token rotation
- Logout invalidation

禁止將 Cookie Domain 設成可造成跨 Partner 洩漏的廣域設定。

---

# 25. CORS

禁止：

```text
Access-Control-Allow-Origin: *
```

對 authenticated APIs 使用 wildcard。

改成 tenant-aware allowlist。

例如：

```text
kuanguard.com
app.kuanguard.com
partner.kuanguard.com
admin.kuanguard.com
portal.megaprotek.com.tw
```

並可由 verified tenant domain 動態產生。

---

# 26. Audit Log

所有敏感行為建立 Audit Log：

```text
actor_id
actor_type
organization_id
action
resource_type
resource_id
ip
user_agent
request_id
before
after
timestamp
```

至少記錄：

- login
- logout
- role change
- customer creation
- project change
- report download
- billing changes
- credit changes
- security campaign
- user invitation
- custom domain
- partner settings

---

# 27. Kuanguard Super Admin

`admin.kuanguard.com`

建立完整：

### SaaS Management

- Merchants
- Stores
- Orders
- Billing
- Payments
- Usage

### Partner Management

- Partners
- Partner Tenants
- Partner Users
- Partner Customers
- Partner Projects
- Partner Credits
- Custom Domains
- Branding
- Commissions
- Billing

### Platform Management

- Feature Flags
- Plans
- Plan Versions
- Integrations
- API Keys
- Webhooks
- Audit
- Security
- System Health

---

# 28. Feature Flags

建立：

```text
feature_flags
tenant_features
plan_features
```

例如：

```text
ordering
reservation
payments
delivery
crm
va
wva
pt
shc
social_engineering
training
partner_portal
white_label
custom_domain
sso
```

不可用 scattered boolean hard-code。

---

# 29. Partner Billing / Credit

保留並完善點數制。

建立：

```text
credit_wallet
credit_ledger
credit_transaction
service_credit_rule
```

Ledger 必須 immutable。

Transaction：

```text
PURCHASE
ALLOCATE
CONSUME
REFUND
ADJUSTMENT
EXPIRE
```

---

# 30. Partner Commission

此次即使不正式啟用，也要建立 schema-ready architecture。

```text
partner_commission_rules
partner_commission_records
partner_settlements
```

支援：

- percentage
- fixed fee
- per customer
- per service
- recurring
- referral

由 feature flag 控制。

---

# 31. 三傑使用流程

```text
megaprotek.com.tw
      ↓
客戶專區
      ↓
portal.megaprotek.com.tw
      ↓
登入
      ↓
Tenant Resolver
      ↓
Megaprotek Tenant
      ↓
Partner Dashboard
      ↓
Customer
      ↓
Project
      ↓
VA / WVA / PT / SHC
      ↓
Finding
      ↓
Remediation
      ↓
Report
```

---

# 32. 三傑客戶使用流程

```text
三傑邀請企業客戶
      ↓
Customer User
      ↓
portal.megaprotek.com.tw
      ↓
Customer Portal
```

客戶只能看：

- 自己公司
- 自己專案
- 自己弱點
- 自己報告
- 自己教育訓練
- 自己社交工程統計

禁止跨 customer access。

---

# 33. White Label Branding

Partner 可設定：

```text
company_name
logo
favicon
support_email
support_phone
legal_name
footer
login_background
brand configuration
```

不要讓 Partner 可以注入任意 JS / HTML。

Logo / asset upload：

- type validation
- size limit
- malware-aware pipeline if available
- object storage
- signed upload
- CDN

---

# 34. Main Website Partner Page

新增：

`/partners`

內容：

> 與 Kuanguard 一起提供更完整的數位服務

Partner 類型：

- Technology Partner
- Security Service Partner
- Reseller
- MSP / MSSP
- Consulting Partner

CTA：

> 成為合作夥伴

> 合作夥伴登入

三傑不是唯一 Partner，也不需要在首頁過度突出。

---

# 35. Main Website Security Positioning

建立：

`/security`

此頁說明 Kuanguard 自身平台安全：

- Encryption
- Authentication
- MFA
- Tenant Isolation
- Audit Logs
- Backup
- Availability
- Privacy
- Secure Development

不要將它混淆為「Kuanguard 對企業直接販售滲透測試」。

---

# 36. Ordering Merchant Architecture

保留既有 Stallorder / Ordering Platform。

Domain model 至少：

```text
organizations
brands
stores
menus
menu_categories
products
product_variants
modifiers
tables
customers
orders
order_items
payments
reservations
memberships
coupons
promotions
printers
delivery_integrations
payment_integrations
```

不要因官網重構影響 order processing。

---

# 37. Merchant Admin

`app.kuanguard.com`

應至少：

- Dashboard
- Orders
- Menu
- Products
- Tables
- QR Code
- Reservations
- Customers
- CRM
- Promotions
- Payments
- Printers
- Integrations
- Reports
- Staff
- Billing
- Settings

---

# 38. Responsive Design

首頁與所有 Login 頁必須：

- Desktop
- Tablet
- iPad
- Android
- iPhone

Mobile-first。

Lighthouse：

- Performance
- Accessibility
- Best Practices
- SEO

不得因動畫造成 Core Web Vitals 明顯下降。

---

# 39. Accessibility

至少：

- semantic HTML
- keyboard navigation
- focus states
- aria labels
- contrast
- form labels
- screen reader friendly
- reduced motion

目標 WCAG 2.1 AA。

---

# 40. 中文優先

主要官網第一階段：

`zh-TW`

架構預留：

- en
- vi

禁止將所有中文 hard-code 在 component。

使用 i18n。

---

# 41. Contact / Lead

首頁 CTA 建立正式 lead flow：

```text
merchant_leads
partner_leads
enterprise_leads
```

欄位：

- type
- name
- company
- phone
- email
- business_type
- store_count
- message
- source
- utm
- status
- assignee
- created_at

---

# 42. Analytics

加入 privacy-aware analytics。

至少：

- page view
- pricing view
- merchant apply
- login click
- partner apply
- CTA conversion

UTM attribution。

不得收集不必要敏感資料。

---

# 43. Legal

建立：

- Privacy Policy
- Terms of Service
- Merchant Terms
- Partner Terms
- Acceptable Use Policy
- Data Processing references
- Cookie Notice（若需要）

Partner 與 Merchant Terms 必須分開。

---

# 44. Branding Boundary

必須在程式架構與 UI 清楚區分：

```text
Kuanguard
= SaaS Platform Provider
```

```text
Megaprotek
= Security Service Partner
```

三傑所提供：

- 弱點掃描
- 滲透測試
- 資安健診
- 社交工程
- 顧問

Kuanguard：

- Platform
- Workflow
- Tenant
- Customer Portal
- Report Management
- Project Management
- Identity
- Billing Infrastructure
- Partner Infrastructure

避免品牌與法律責任混淆。

---

# 45. UI Navigation

## Public Website

```text
Kuanguard Logo

產品功能
解決方案
收費方式
合作夥伴
關於我們

[登入]
[免費開始]
```

## Login

```text
商家登入
合作夥伴登入
平台管理員
```

不要把企業資安模組直接放在公共首頁主 navigation。

---

# 46. Migration Strategy

執行前：

1. inventory current routes
2. inventory current API
3. inventory auth
4. inventory tenant schema
5. inventory billing
6. inventory security platform
7. inventory ordering platform
8. inventory deployment
9. inventory DNS assumptions

建立：

`docs/MIGRATION_PLAN.md`

所有原 URL 若有 public traffic：

建立 redirect mapping。

禁止造成大量 404。

---

# 47. Backward Compatibility

舊資安 URL：

若目前仍使用：

```text
/security/*
/va
/wva
/pt
/shc
```

不要直接刪除。

依使用情境：

- 301 到 Partner 說明
- authenticated route 保留
- legacy alias
- admin-only route

列入 migration table。

---

# 48. Database Migration

所有 schema changes：

- timestamped migration
- reversible where possible
- no destructive drop
- indexes
- unique constraints
- foreign keys
- tenant constraints

Production data 不得 wipe。

---

# 49. Testing

必須新增：

## Unit

- tenant resolver
- domain resolver
- RBAC
- billing
- login router
- feature flags

## Integration

- Merchant login
- Partner login
- Custom Domain
- Megaprotek tenant
- Customer isolation
- OAuth callback
- API CORS

## E2E

### Merchant

```text
Homepage
→ Login
→ Merchant
→ Orders
```

### Partner

```text
partner.kuanguard.com
→ Login
→ Partner Dashboard
```

### Megaprotek

```text
portal.megaprotek.com.tw
→ Login
→ Megaprotek Tenant
→ Customer
→ Project
```

---

# 50. Security Tests

測試：

- horizontal privilege escalation
- vertical privilege escalation
- tenant breakout
- IDOR
- open redirect
- OAuth state
- CSRF
- XSS
- CORS
- upload
- rate limit
- brute force
- session reuse

---

# 51. Deployment

不得直接破壞 production。

至少：

```text
development
staging
production
```

先 staging。

建立：

`staging.kuanguard.com`

以及 Partner staging custom domain strategy。

---

# 52. Observability

加入：

- structured logs
- request ID
- error tracking
- health endpoint
- uptime monitoring
- audit trail
- deployment version

不得在 log 中記錄：

- password
- access token
- refresh token
- secret
- payment sensitive data

---

# 53. Required Deliverables

Codex 完成後必須輸出：

```text
docs/
├─ ARCHITECTURE.md
├─ BRAND_ARCHITECTURE.md
├─ MIGRATION_PLAN.md
├─ PARTNER_PLATFORM.md
├─ CUSTOM_DOMAIN.md
├─ MEGAPROTEK_INTEGRATION.md
├─ CLOUDFLARE_SETUP.md
├─ AUTH_ARCHITECTURE.md
├─ MULTI_TENANT_SECURITY.md
├─ BILLING.md
├─ RBAC.md
├─ DEPLOYMENT.md
├─ TEST_REPORT.md
└─ MANUAL_ACTIONS_REQUIRED.md
```

另更新：

```text
README.md
CHANGELOG.md
.env.example
```

---

# 54. MANUAL_ACTIONS_REQUIRED

所有需要專案擁有者人工執行的項目統一放最後。

例如：

- GoDaddy DNS
- Cloudflare nameserver
- Cloudflare API token
- Megaprotek DNS
- OAuth provider credentials
- LINE Login
- Google OAuth
- Apple Sign In
- Microsoft Entra
- payment merchant credentials
- foodpanda/Uber Eats official credentials
- production secret
- domain verification

Codex 不得因缺少這些 credentials 而停止其餘可完成的工作。

---

# 55. 第一階段優先級

## P0

- kuanguard.com 首頁重新定位
- Ordering SaaS Landing Page
- Unified Login
- Partner Portal
- Multi-Tenant
- Megaprotek Tenant
- portal.megaprotek.com.tw support
- RBAC
- Auth Routing
- Security
- Migration

## P1

- Partner Dashboard
- Customer Portal
- VA/WVA/PT/SHC integration
- Project Management
- Credits
- White Label
- Feature Flags
- Audit

## P2

- Partner Commission
- Enterprise SSO
- Advanced CRM
- Advanced Analytics
- Referral
- Partner onboarding automation

---

# 56. 最終驗收標準

完成時必須符合：

### Kuanguard Public

`kuanguard.com`

第一眼呈現：

> 商家 SaaS / 點餐 / 營運平台

而不是：

> 資安服務公司

### Merchant

`app.kuanguard.com`

可管理商家 SaaS。

### Partner

`partner.kuanguard.com`

可登入合作夥伴平台。

### Megaprotek

`portal.megaprotek.com.tw`

可映射到三傑 Partner Tenant。

### Kuanguard Admin

`admin.kuanguard.com`

可統一管理：

- Merchant
- Partner
- Tenant
- Billing
- Domain
- Feature
- Security
- Audit

---

# 57. 禁止事項

禁止：

1. 重建整個專案。
2. wipe database。
3. 建立 Megaprotek 專用 fork。
4. duplicate backend。
5. hard-code tenant。
6. hard-code pricing。
7. hard-code domains。
8. frontend-only tenant security。
9. wildcard authenticated CORS。
10. 將 secrets commit 到 Git。
11. 未測試直接 production deploy。
12. 因缺少外部 credentials 中斷整體工作。
13. 刪除目前資安 SaaS。
14. 刪除目前 Ordering SaaS。
15. 宣稱尚未正式串接的 payment / food delivery service 已可 production 使用。

---

# 58. 最終工作方式

直接開始執行。

不要在每個 Phase 停下來詢問。

可安全自動完成的工作全部完成。

僅將真正必須由 Owner 提供帳號、DNS、credential、商業決策或第三方核准的工作列入：

`MANUAL_ACTIONS_REQUIRED.md`

完成後輸出：

1. 已修改內容
2. 新架構
3. Migration 結果
4. Database changes
5. Route changes
6. Auth changes
7. Partner changes
8. Megaprotek integration
9. Security changes
10. Test results
11. Build result
12. Deployment status
13. Manual actions
14. Known limitations

最終目標：

> 將 Kuanguard 由單一企業資安服務官網，升級為可同時承載商家 SaaS 與 B2B Partner Ecosystem 的 SaaS Platform；公共品牌以點餐與商家營運為核心，而企業資安功能透過 Partner Portal 提供，三傑科技作為第一個正式 Security Service Partner，未來可擴充至更多合作夥伴，且不需要複製系統或建立新的 codebase。
