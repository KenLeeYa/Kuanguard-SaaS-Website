# 現況與增量檢查點

日期：2026-09-10，Asia/Taipei。

原始工作目錄為空；本次任務建立的程式現存於同一個 `KuanGuard` 目錄。v1.1 到達時已存在的 API/UI、資料表、兩租戶合成資料、報告樣本、PostgreSQL/Redis 和備份成果全部保留。v1.1 檢查點的 Git 為 `main`、當時尚無初始 commit／remote；未提交檔案皆歸本次任務，不混入其他產品工作樹。完成驗證後建立本機交付 commit，使用 `git rev-parse HEAD` 查詢；無 push 或遠端部署。沒有 `.codegraph/`，未擅自建立索引。

原需求檔存為 `implementation-spec.md`；增量檔存為 `update-spec-v1.1.md`。原檔 SHA-256 分別為 `e893a88a9bb8d4e072846a36e7b1f7204b5b48db2e81fc6eaa9c381255a862a1`、`789016b656a26f5ccbc6c7af25cb05054cc9e423fe8c5370a103222f9ba115bb`。

## 執行位置

| 元件 | 實際現況 | 正式目標 |
| --- | --- | --- |
| 官網／客戶／學員 UI | Next.js，loopback 3180 | 既有 Vercel Team 內獨立 Projects，DNS-only |
| 內部 UI／API／worker | 同 repo，API loopback 8180；獨立容器配置 | 專用主機；admin Tunnel + Access + app auth |
| 資料庫 | 專用 Compose PostgreSQL，loopback 55438，非 owner app role | 既有 Supabase Org 內專用 Project |
| Queue | Redis loopback 6388；DB jobs/outbox 為事實來源 | KUANGUARD 專用 queue；目前 worker 直接輪詢 DB |
| 檔案 | `.local/storage`，透過授權 API 下載 | 分環境 private R2；完整 lifecycle 待啟用 |
| 其他產品 | QIDAIGO 僅清冊／來源端提案及 read-only summary contract | 不共用 DB、商店、點數、session 或 admin key |

## Migration

`0001_initial` 凍結原始 schema。`0002_review_policy` 新增合約獨立覆核政策；`0003_portfolio_projection` 新增有 FORCE RLS 的彙總快取；`0004_retest_verification` 新增個別複測證據；`0005_worker_claim_token` 新增可空 claim token；`0006_service_ledger_immutable` 保護服務額度 ledger。接回原任務後再新增 `0007_drafts_tickets`、`0008_training_rights`、`0009_project_execution`、`0010_tenant_lifecycle`，保留原表資料。

所有增量採向前相容策略；既有 rows、object hashes、已完成 jobs、未知寄送、點數 ledger 和 publication 沒有重設。舊 worker 的 NULL claim 會進入保守 recovery，未知接受不重送。回復前端／程式時保留新增欄位，不執行 destructive down migration。還原只寫入另一個明確命名的 disposable DB。

## Phase 狀態

| Phase | 保留／接續結果 | 真實缺口 |
| --- | --- | --- |
| 0–1 | 清冊、模型、ADR、RBAC/RLS、四入口、lockfiles、CI 配置 | 真實 IdP／部署 membership、remote CI |
| 2–3 | 官網、詢價、CRM、報價、合約、批次、額度、排程、變更、驗收、待辦依賴／決議、技能／容量檢查與工時成本 | 正式員工／設備資料、假日及 SLA／共用工具政策 |
| 4–5 | 五種資料匯入、核定快照、五格式交付、複測、更正 | 正式模板、完整 Office 字型／逐頁 QA、真實樣本 |
| 6 | 共用點數、独立服務額度、sandbox 支付／退款／對帳 | 商店／發票實接與核定計費政策 |
| 7–8 | 演練 sandbox、判讀／補救與文字課程／測驗／證明、有限內含／贈送／人工課程席次及學員離職／調部門 | 既有 Gophish 核心實接、真實 SMTP、影片／字幕與教材上架 |
| 9 | 客戶結果、討論、通知、工單對話、供應商問卷、短期server草稿、授權匯出／退場／分階段erase executor | 真實企業驗證／邀請、正式資料保存及安全交付政策 |
| 10–11 | 本機七服務 UAT、實際備份還原、可審閱映像與部署差異 | 公網資源／DNS 切換／TLS／付費提供者／全項正式 UAT |

沒有重跑全部 Phase 0，也沒有將有效程式退回 mock。sandbox 原本即屬未啟用外部 provider 的明示狀態。

最終本機檢查點：214 tests＋45 subtests、前端10 tests／typecheck／production build、158 paths OpenAPI 與新增5組 HTTP checks通過。三個容器全部來源雜湊相符；80張表／811筆／36個物件在独立資料庫還原比對成功，0001～0010 revisions保留，原兩份備份未變。3180 現為 `DEPLOYMENT_SURFACE=local` 的正式建置，本機限定使用；API/worker 已從新來源啟動。最新證據索引見 `release-readiness.md`。
