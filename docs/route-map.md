# KUANGUARD route map

前端根目錄 `apps/web`，Next.js 16.3.4 / React 19.3.0 / TypeScript 5.9.3。本文件已合併 2026-09-10 v1.1 增量；原七服務 UI 保留。

## 部署入口

| 模式 | 路由與限制 |
| --- | --- |
| `DEPLOYMENT_SURFACE=local` | 本機 `http://127.0.0.1:3180`，公開、客戶、學員及 `/admin/*` 共用本機 UI。API 由 `/api/*` 轉送 `http://127.0.0.1:8180/*`。 |
| `DEPLOYMENT_SURFACE=public` | Vercel 官網/客戶/學員；`/admin`、`/portfolio`、內部路由與 `/api/internal` 回 404。`VERCEL` 存在時不允許切成 internal/local。 |
| `DEPLOYMENT_SURFACE=internal` | 資安專用容器；admin host 的 `/overview`、`/portfolio` 等重寫至 `/admin/*`。API 仍獨立要求 Access JWT、session 與職務/專案權限。 |

`app.kuanguard.com/` 導向 `/dashboard`；該 host 的 `/services` 對應已購服務額度 `/entitlements`。公開 `/services` 為七服務目錄。`www.kuanguard.com` 永久導向根網域並保留 path/query。DNS-only Vercel 不宣稱被 Cloudflare Access/WAF 保護。

本機 API proxy 不複製業務規則。瀏覽器沒有 DB、Gophish 或供應商管理密鑰。公開與內部部署須分別配置正確 API origin；實際正式部署與主機綁定尚待驗證。

## 公開網站

| 路由 | 已實作 |
| --- | --- |
| `/` | 原創 hero、七服務、工程師/自助流程、年度方案、合成工作台示意、信任、FAQ、詢價入口 |
| `/services` | 全部／工程師交付／線上自助篩選 |
| `/services/va`, `/wva`, `/shc`, `/pt`, `/source-code`, `/phishing`, `/training`（均接於 `/services`） | 適用範圍、準備、流程、交付、資料邊界與詢價 |
| `/plans/annual-security` | 七項範圍、頻率、額度與追加方式；未核定價格顯示詢價 |
| `/courses`, `/courses/[id-or-slug]` | 真實公開課程 API 與文字預覽 |
| `/pricing/credits` | 計費單位、預留/耗用與尚待核定政策 |
| `/request-quote` | 服務選擇、公司/窗口/email/範圍/日期；實際寫入 lead |
| `/resources`, `/trust`, `/about`, `/contact` | 資源、資料政策、啟用狀態及真實公司資料邊界 |
| `/legal/privacy`, `/terms`, `/credits`, `/acceptable-use`, `/data-processing`（均接於 `/legal`） | 標示開發版政策與生效邊界 |
| `/login` | 依 `/auth/providers` 顯示正式 provider；開發角色僅由 `/auth/dev/profiles` 啟用 |

公開 HTML 由 Next SSR 產生，有 canonical、metadata、sitemap。私有結果不列入 sitemap，且禁止索引；robots 不作授權機制。

## 客戶與學員

| 路由 | 角色 | 功能/API |
| --- | --- | --- |
| `/dashboard` | customer_contact | `/customer/dashboard`，七服務、近期行程、發布風險與有權點數 |
| `/projects`, `/projects/[id]` | customer_contact | 列表、工作包、批次、範圍、時程、發布結果/報告、文字討論、驗收 |
| `/projects/[id]/changes` | customer_contact | 範圍與改期申請、費用版本比較與明確接受；PM 套用後更新排程／範圍 |
| `/calendar` | customer_contact | `/customer/calendar` 的已確認時程 |
| `/findings`, `/findings/[id]`, `/assets` | customer_contact | 已發布資料、版本、修補文字、複測申請 |
| `/reports` | customer_contact | 帶版本五格式授權下載與更正版標示 |
| `/phishing/campaigns`, `/phishing/campaigns/[id]` | campaign_manager | 草稿、排程、預留、暫停/繼續/取消、事件人工判讀與依據；同時具 training_manager 可確認補救派課 |
| `/phishing/groups` | campaign_manager | 專用 CSV／XLSX 名單匯入，無效/重複列說明；不建立管理帳戶 |
| `/phishing/report` | campaign_manager | 可疑郵件文字回報 |
| `/training` | training_manager | 實際課程、學員、派課確認、授權取消與學習紀錄 |
| `/wallet`, `/orders` | billing_manager | 批次/用途/交易、購點確認、sandbox 支付驗證與訂單 |
| `/quotes`, `/contracts`, `/entitlements` | customer_contact | 報價版本確認、合約與獨立服務額度 |
| `/organization`, `/onboarding` | customer_admin | 目前企業與角色查詢；正式企業認領/邀請待 IdP 流程 |
| `/support`, `/support/[id]` | 授權客戶角色 | 自己提出的文字工單、目前狀態與客戶可見對話；內部備註不下發 |
| `/organization/learners` | customer_admin/training_manager | 學員與部門查詢；只有 customer_admin 可調部門／離職，保留歷史和其他 tenant 身分 |
| `/organization/data` | 對應授權客戶角色 | 分頁匯出授權結果；只有 customer_admin 可提交匯出／退場申請 |
| `/questionnaires`, `/questionnaires/[id]` | customer_admin | 建立企業／供應商問卷，帶 revision 的文字回覆與證據參考 |
| `/notifications`, `/learn/notifications` | 對應登入角色 | 使用者專屬通知與已讀狀態 |
| `/learn`, `/learn/courses` | learner | 僅自己的課程與證明；相容 OIDC 學員導向 |
| `/learn/courses/[enrollment_id]` | learner | 啟動、文字章節、伺服器驗證進度、確認測驗、結果 |
| `/learn/certificates/[id]` | learner | 私有完課紀錄及 JSON 證明紀錄下載 |

客戶 VA/WVA/SHC/PT/源碼皆無原始資料上傳與掃描控制。客戶演練名單匯入是不同業務端點：上限 2 MB／10,000 筆；Excel 單工作表且拒絕公式、巨集與外部連結。問卷證據參考只保存文字，不下載或開啟外部 URL。前端可見性與 API 授權雙層檢查。

## 內部與公司總覽

以下本機加 `/admin`；admin host 可由根路徑使用。

| 路由 | 角色 | 功能 |
| --- | --- | --- |
| `/overview` | pm/engineer/reviewer/finance | 真實授權專案與待覆核/交付/未指派摘要 |
| `/projects`, `/projects/[id]` | pm/engineer/reviewer | 專案與批次；PM 可核定有限服務額度、建立／取消／更正批次與派工；指派工程師可用既有來源重送覆核 |
| `/crm`, `/quotes` | pm | 詢價 lead、報價與新版本 |
| `/dispatch` | pm | 工程师/覆核資格、有效期限、交通緩衝、工具容量與專案排程入口 |
| `/training` | pm | 有限年度內含／贈送／人工課程席次及使用狀態 |
| `/billing/project-costs` | pm/finance＋project grant | 預估／實際工時成本，依有效合約與已登錄成本顯示毛利或未知原因 |
| `/administration/lifecycle` | 同時 pm＋finance | 退場申請審核、短效計畫與版本摘要、撤銷存取及保存條件；CLI 執行精確清冊 erasure |
| `/changes` | pm | 變更費用新版本、客戶確認後套用追加範圍／完整派工與衝突檢查 |
| `/imports` | engineer | 本機文字檔匯入、範圍確認、SHA-256、解析預覽、coverage、提交 |
| `/review`, `/shc`, `/pt`, `/source` | reviewer/engineer 分權 | 來源結果對照與按專案政策核定；覆核動作限 reviewer |
| `/retests` | pm/engineer/reviewer 分權 | PM 確認複測資格並建立來源關聯批次；覆核者以原方法、範圍與規則證據驗證，未覆蓋時拒絕 |
| `/reports` | reviewer/engineer 分權 | 背景產製工作、QA/五格式預覽、明確確認後發布；產製/發布限 reviewer |
| `/billing` | finance | 支付/點數對帳、退款確認與狀態、發票未啟用狀態 |
| `/phishing-operations` | finance | unknown 供應商接受狀態對帳，核對紀錄／時間／依據後扣點或釋放，不重寄 |
| `/questionnaires`, `/questionnaires/[id]` | reviewer | 以最新 revision 記錄覆核、需補充或證據不足；無證據不能核定 |
| `/tickets`, `/tickets/[id]` | pm | 工單內容與帶原始狀態檢查的進度更新；原因留於稽核 |
| `/notifications` | 對應內部角色 | 僅自己的通知 |
| `/integrations`, `/audit` | 明示職務 | 能力/未啟用狀態及真實 actor 稽核 |
| `/portfolio`, `/portfolio/products`, `/portfolio/finance`, `/portfolio/tasks`, `/portfolio/operations`, `/portfolio/costs`, `/portfolio/integrations` | portfolio_owner | KUANGUARD/QIDAIGO 唯讀彙總、產品切換、來源時效/口徑、刷新/停用 connector |

同一 actor 可兼任 PM/工程師/覆核/財務；不虛構第二個管理者。是否必須不同覆核者依 `project.requires_independent_review` 的後端政策。portfolio_owner 不會隱含給予任何專案證據權限。

## 實際驗證與尚待驗證

- 已通過：TypeScript、Next production build、deployment surface/對比測試、HTTP SSR/API 契約 smoke。
- HTTP smoke：23 公開路由；客戶與學員對內部/portfolio API 被拒；owner 七總覽路由；未連線 QIDAIGO 與 null 合併金額；詢價真入 PM 後台；無效 CSRF 被拒。
- 正式 surface 的本機 origin/假 alias/admin host 阻擋及 no-store 驗證記錄於 `apps/web/evidence/public-surface-smoke.json`；此為本機生產模式測試，不代表 Vercel、DNS 或 Access 正式部署已完成。
- 正式 surface 針對路由/編碼路徑/HTTP Host 組合阻擋、私有頁面 no-store/noindex、www 路徑與 query 保留及 app 入口導向測試，實際最新數量依 evidence receipt。
- 增量 HTTP smoke 已通過：XLSX 有效／無效列、unknown 對帳冪等、問卷答案 revision／跨企業隔離、工單狀態衝突、個人通知，以及服務額度→變更報價→客戶接受→套用範圍→取消釋放。會建立標示為合成的本機紀錄，沒有真實寄信或付款。
- 瀏覽器與視覺驗證被 CUA 管理政策檢查阻擋，390/768/1440 實測、完整鍵盤流程與 screenshots 待恢復後補驗。
- 活動／派課／購點使用24小時 server 草稿與 CAS 衝突處理，GET/PUT/DELETE `/app/drafts/{kind}/new` 僅存目前 tenant＋actor 的允許欄位；沒有宣稱全站任意表單均有草稿。
- 沒有聲稱已完成：正式 IdP/邀請、正式付款/發票/SMTP/Stream/R2、可售影音教材、正式電子簽署、所有原規格選配管理頁。七核心本機功能已接真實 API；完整正式 release gate 尚未通過。

## 啟動與建置設定

本機 `npm ci --ignore-scripts`、`npm run dev` 在 3180；正式模式先 `npm run build`，再設定 `DEPLOYMENT_SURFACE` 與 `PORT` 後執行 `npm start`。start script 使用 Next standalone，複製本專案靜態檔案至 standalone 目錄後啟動，不使用不相容的 next start shortcut。

`API_INTERNAL_URL` 由 Next 在 build 階段凍結 rewrite。內部容器 build 使用專用 API 服務 origin；Vercel build 使用已核定的 `https://api.kuanguard.com`。不接受帶帳密/path/query/fragment 的 origin，不接受 QIDAIGO origin；不得僅在 runtime 修改後就宣稱 API 目的地已改變。
