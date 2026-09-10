# KUANGUARD

KUANGUARD 數位科技官網，旗下提供商家 SaaS、合作夥伴平台與企業資安服務。主站以產品與平台為入口，點餐系統是其中一項產品。N 家 Partner 共用程式、獨立客戶歸屬與授權；原七服務、學員、內部工作台與 Portfolio 保留。合成資料明示用途，正式共同 release gate 仍關閉。

## 直接使用

目前工作區分工：官網樣式由另一工作區執行；此區接續資安系統架構與七服務。原 Phase 0～9 已有實作但仍有工程／驗收缺口，Phase 10～11 正式部署與啟用未完成。詳 [資安 Phase 狀態](docs/SECURITY_PHASE_STATUS.md) 與 [資安架構](docs/SECURITY_ARCHITECTURE.md)。新增內部 `GET /internal/operations/health` 維運彙總與 Redis 共用限流。

- 本機入口：<http://127.0.0.1:3180>
- 點餐產品：<http://127.0.0.1:3180/products/ordering>，保留原本簡潔的商家頁面；[公司官網設計與參考](docs/CORPORATE_WEBSITE_DESIGN.md)。
- 登入頁：<http://127.0.0.1:3180/login>，分流商家、Partner、平台管理及既有資安客戶／學員。
- Partner：<http://127.0.0.1:3180/partner/login?partner=megaprotek>；選三傑示範角色。Platform admin：<http://127.0.0.1:3180/admin/platform>。
- 內部公司總覽：<http://127.0.0.1:3180/admin/portfolio>；正式目標為 `admin.kuanguard.com/portfolio`。
- API health：<http://127.0.0.1:8180/health>；OpenAPI：[docs/openapi.json](docs/openapi.json)。

Windows PowerShell，在本專案目錄執行：

```powershell
uv sync --locked
pwsh -File scripts/start-local.ps1
```

啟動器保留現有 `.env`、PostgreSQL/Redis volumes 和已占用的服務 ports；migration 只套用尚未執行的編號增量，seed 遇到既有企業即保留，不重設資料。只啟動本專案的 API、worker、UI；不停止共用 Docker。依賴 Docker Desktop、Node 24、uv 與 PowerShell 7。首次安裝會產生本機隨機 secrets，不印出其值。

```powershell
uv run pytest
uv run ruff check backend scripts tests
uv run python scripts/export_openapi.py --check
npm --prefix apps/web run typecheck
npm --prefix apps/web test
npm --prefix apps/web run build
```

`scripts/live_uat.py --run` 只對固定 loopback API 新增合成驗收資料，使用 `.local/live-uat-state.json` 接續已完成步驟，不重新跑成功交易。它會消耗合成點數、產出本機報告及等待真實學習時間，並保留結果供 UI 操作。一般使用不需重跑。

## 已連通流程

1. 詢價 → PM 報價版本 → 客戶確認／合約 → 七服務工作包 → 有限批次額度與排程 → 變更範圍／費用確認 → 單批驗收。
2. VA、WVA、SHC、PT、SOURCE：工程師匯入 → 安全解析／錯誤預覽 → 覆核 → immutable snapshot → durable worker 產製 DOCX/PDF/PPTX/XLSX/CSV → 發布 → 授權下載／文字修補 → 複測證據 → 更正版本保留。
3. 演練：CSV/XLSX 名單 → 排程預留 → sandbox 接受／拒絕／未知 → 人類／設備判讀 → 補救派課。未知寄送需憑供應商證據對帳，不能盲目重寄。
4. LMS：優先取適用內含／贈送／人工席次，否則預留點數 → 首次啟動扣一次 → 伺服器進度與測驗 → 完課證明；到期／離職僅釋放未啟動授權，歷史保留。
5. 問卷文字證據／版本覆核、個人通知、工單對話與內部備註；專案待辦依賴／會議決議、派工资格／工具容量、工時與成本。Portfolio 只讀已授權彙總；QIDAIGO 未連線時顯示未知。
6. 活動／派課／購點有短期伺服器草稿及衝突保護；客戶可匯出授權資料及提出退場申請。退場與精確清冊 erasure 分開，正式保存與備份條件未核定就不執行刪除，詳 [資料生命周期](docs/data-lifecycle.md)。

## 交付與限制

[需求與驗收矩陣](docs/requirements-traceability.md)、[release readiness](docs/release-readiness.md)、[增量狀態](docs/update-v1.1-status.md)、[啟用清單](docs/activation-checklist.md) 是完成範圍與後續啟用依據。

Partner 更新交付：[架構](docs/ARCHITECTURE.md)、[品牌](docs/BRAND_ARCHITECTURE.md)、[遷移](docs/MIGRATION_PLAN.md)、[Partner 操作](docs/PARTNER_PLATFORM.md)、[Auth](docs/AUTH_ARCHITECTURE.md)、[安全](docs/MULTI_TENANT_SECURITY.md)、[RBAC](docs/RBAC.md)、[Billing](docs/BILLING.md)、[Custom domain](docs/CUSTOM_DOMAIN.md)、[三傑](docs/MEGAPROTEK_INTEGRATION.md)、[Cloudflare](docs/CLOUDFLARE_SETUP.md)、[測試](docs/TEST_REPORT.md)、[部署](docs/DEPLOYMENT.md)、[必要人工項目](docs/MANUAL_ACTIONS_REQUIRED.md)。新環境需明示執行 `uv run python scripts/seed_partners.py` 安裝合成 Partner；現有環境已完成。

正式 IdP、Gophish/SMTP、支付／發票、R2/Stream、公司核准模板／教材與獨立雲端 Projects 尚待設定及實接驗證。Native AppScan 專有格式並未宣稱支援；WVA 支援已明示的映射 XML。管理政策阻擋瀏覽器自動化，尚無 390/768/1440 視窗、完整鍵盤與錄影驗證。Partner commission／enterprise SSO 等 P2 只提供停用 schema foundation。

後續部署沿用既有 Cloudflare Account、Vercel Team、Supabase Organization，但採 KUANGUARD 專用 Projects/DB/queue/storage/secrets。現有 QIDAIGO 原始碼、資料庫與部署未修改。原始碼同步至 [KenLeeYa/Kuanguard-SaaS-Website](https://github.com/KenLeeYa/Kuanguard-SaaS-Website)，CI 以提交 SHA 查詢；GitHub 同步不代表正式服務已上線。
