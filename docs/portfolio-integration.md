# 公司總覽與唯讀來源整合

版本 v1.1，日期2026-09-10。公司總覽保留原資安 `/overview`，增加 `/portfolio`、products、finance、tasks、operations、costs、integrations。API 為 `/internal/portfolio` 同名子路由。

所有總覽路由要求已驗證 `portfolio_owner`，在既有登入、tenant、Origin/CSRF與稽核控制內運作。單人同時具有工程師或覆核者角色不自動授予 portfolio_owner，portfolio_owner 也不自動取得專案 grant、weakness、受測名單或原始碼。KUANGUARD 只彙總目前已授權 tenant；目前不接受請求指定其他 tenant，未實作自動跨所有客戶彙總。

`backend/kuanguard/portfolio.py` 是唯讀業務彙總與來源 adapter；`portfolio_routes.py` 提供 API。QIDAIGO 不直連 DB、不取得管理 API key、不抓取 merchant dashboard，未提供 source URL/憑證時回傳 disconnected、null 待辦和空 metrics，不顯示零營收或綠燈。KUANGUARD 本地 SQL 只查計數與金額，輸出不含客戶/合約/訂單名稱、發現或名單。

## HTTP 契約

GET `/internal/portfolio`、`/products`、`/finance`、`/tasks`、`/operations`、`/costs`、`/integrations`、`/connectors` 回傳：

```json
{"items":[],"environment":"development","combined_financial_total":null,"notice":"各指標分開列示","updated_at":"UTC ISO timestamp"}
```

每個產品物件帶 product、label、environment、scope、status、source_at、synced_at、expires_at、complete、synthetic、metrics、health、tasks、costs、deep_link、reason。status 為 connected/disconnected/stale/error/revoked。metrics 含 key、label、value、unit、currency、tax_basis、definition_version、period_start/end、timezone、measurement、verified。資料不足用 value=null，不以零替代。

GET `/connectors/{kuanguard|qidaigo}` 查單一來源。POST `/connectors/{product}/refresh` 執行一次驗證及刷新；POST `/connectors/{product}/disable` 撤銷該本機 connector。POST 使用既有 `X-CSRF-Token`、Origin、Idempotency-Key，可無 body 或傳 `{}`；來源URL、tenant、環境、scope或憑證不可透過 body/query 指定。HTTP GET 不向遠端刷新。

refresh idempotency 僅存 `{product,status}` receipt；重送時重新檢查目前授權與TTL，不保存或重播舊財務 payload。停用清除 projection；同舊 QIDAIGO grant 不可重新刷新，需配置新核定 grant 後由 owner 明確刷新。KUANGUARD 本機 projection 可由 owner 明確刷新恢復。外部深連結只接受設定中的 HTTPS allowlist host，無 session/query。

## 來源驗證與資料生命週期

QIDAIGO 僅對固定 allowlist HTTPS endpoint 發出一個 GET。timeout 預設2秒、上限5秒，response 限128KiB，不追隨redirect，不使用環境proxy。JWT 固定 HS256、issuer=qidaigo-summary、audience=kuanguard-portfolio、sub=portfolio-readonly；驗證 exp/iat/jti、product=qidaigo、environment、scope=portfolio.summary.read與tenant_scope。另用 nonce、response timestamp及獨立 HMAC key 驗證回應原文，拒絕重播與錯誤簽章。

配置範圍 `qidaigo_owner_tenant_id` 必須等於目前已驗證的KUANGUARD tenant。此值與來源 tenant_scope 是受限 connector 信任設定，前端不可自報。JWT 金鑰與回應金鑰是專用唯讀整合憑證，不複用產品 admin credential。正式環境拒絕 synthetic=true 來源。

最小快取表為 `portfolio_connectors`，欄位 tenant/product/environment、grant_binding hash、projection、status、source/sync/expiry時間、generation、error_code；不保存原始來源body或token。TTL預設300秒；過期GET立即停止顯示數字。`prune_expired_projections(conn, verified_tenant_id, now)` 給現有worker按已驗證租戶清除到期projection；刷新error/stale/revoked與停用也會清除。來源401/403為revoked；timeout/network為error；未配置為disconnected；TTL或source_at過期為stale。一個來源故障不阻塞另一產品彙總。

資料表使用本模組 `portfolio_metadata` 與 `PORTFOLIO_TABLES`，需透過主專案的增量migration建立及加入RLS，不在請求內create_all。資料備份應包含這個metadata；快取本身可從來源重建，撤銷狀態與稽核須保留。開發測試使用獨立記憶體SQLite，未由此模組對現有DB套migration。

## 財務定義

QIDAIGO：gmv是訂餐交易總額，platform_fees_accrued是應計服務費，platform_fees_received是實收服務費，refunds是訂單交易退款額，四者不相加成收入。只接受 `qidaigo.<key>/1` 核定DTO版本，未知或重複definition、unit、period拒絕。來源尚未核定的費率或月上限由來源保留，總覽沒有寫入費率的API。

KUANGUARD：contracted_amount為當期成立合約額；points_purchase_cash與points_purchase_refunds來自現有付款/退款紀錄；points_purchased只計有訂單關聯的付費lot；points_reserved是當下帳本預留餘額；points_consumed是當期耗用。資安服務的cash_received/refunds/accounts_receivable因尚缺服務合約收款帳關聯，明示null。購點與耗用不重複當收入。金額用minor_currency，點數用points。時段以Asia/Taipei定義當月起點，再以UTC保存。

`combined_financial_total` 始終為null；目前沒有收入認列核定，不提供正式財報或跨產品總收入。稅基未知的金額明示unknown。SaaS帳單/成本/預算未接入時costs.status=not_configured，而非零成本。

## 設定與啟用

配置於部署secret manager或本機未提交的.env，空值保持未連線：

```dotenv
PORTFOLIO_ENVIRONMENT=development
PORTFOLIO_CACHE_TTL_SECONDS=300
PORTFOLIO_SOURCE_MAX_AGE_SECONDS=900
PORTFOLIO_TIMEOUT_SECONDS=2
PORTFOLIO_QIDAIGO_URL=
PORTFOLIO_QIDAIGO_ALLOWED_HOSTS=
PORTFOLIO_QIDAIGO_TENANT_SCOPE=
PORTFOLIO_QIDAIGO_OWNER_TENANT_ID=
PORTFOLIO_QIDAIGO_TOKEN=
PORTFOLIO_QIDAIGO_TOKEN_KEY=
PORTFOLIO_QIDAIGO_RESPONSE_KEY=
PORTFOLIO_QIDAIGO_DEEP_LINK=
```

需先核定來源端最小patch、部署唯讀endpoint、確認來源定義和UTC/台北期間差異，簽發受限credential，再由owner刷新驗證。沒有依此文件更動QIDAIGO程式、DB、登入、出單、費率或正式部署。來源盤點憑據在 `infra/evidence/qidaigo-readonly-baseline-20260910.json` 與 `docs/shared-saas-inventory.md`。

驗證：`python -m pytest backend/tests/test_portfolio.py -q`，30 tests通過；scoped Ruff通過。含兩tenant、無隱含專案存取、JWT/URL/scope互換、簽章、過期/timeout/revoke、TTL清除、錯誤metric、CSRF、idempotent replay及新grant重新啟用。這些是合成來源契約測試，未宣稱來源正式API已連線。
