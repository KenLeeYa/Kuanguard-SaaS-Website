# KUANGUARD

七服務資安平台的可操作本機版本，已增量套用 v1.1。官網、客戶、學員、內部工作台及公司 Portfolio 共用程式，依部署面與已驗證角色隔離。所有現有示範資料、點數與報告均明示合成用途；正式七服務共同 release gate 仍關閉。

## 直接使用

- 本機入口：<http://127.0.0.1:3180>
- 登入頁：<http://127.0.0.1:3180/login>，選「示範單一管理者」操作 PM／工程師／覆核／財務與 Portfolio；選企業 A 或學員 A 驗證客戶／學習流程。
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

正式 IdP、Gophish/SMTP、支付／發票、R2/Stream、公司核准模板／教材與独立雲端 Projects 尚待設定及實接驗證。Native AppScan 專有格式並未宣稱支援；WVA 支援已明示的映射 XML。管理政策阻擋瀏覽器自動化，尚無 390/768/1440 視窗、完整鍵盤與錄影驗證。CI workflow 已建置，尚未推送至遠端執行。

後續部署延用既有 Cloudflare Account、Vercel Team、Supabase Organization，但採 KUANGUARD 專用 Projects/DB/queue/storage/secrets。現有 QIDAIGO 原始碼、資料庫與部署未修改。本機交付版本以 `git rev-parse HEAD` 查詢；repo 尚無 remote，不能把本機 commit／驗證當成正式發布收據。
