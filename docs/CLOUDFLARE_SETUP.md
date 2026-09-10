# Cloudflare 部署接入

沿用既有 account 的核對與 DNS plan/apply 工具；每次變更仍綁定 KUANGUARD zone、完整權威 DNS 匯出、不可變 plan 與 fresh readback。既有結果見 [cloudflare-status.json](cloudflare-status.json)、[cloudflare-cutover](cloudflare-cutover.md)。本輪沒有寫入 Cloudflare、GoDaddy 或 Megaprotek DNS；舊 discovery 是歷史快照，啟用前須更新。

| 目的地 | 接入方式 | 快取／保護 |
| --- | --- | --- |
| kuanguard.com、www | 公開 Next 部署；www 308 保留 path/query | 僅 immutable static assets |
| partner、auth、自訂 Partner host | 共用 public surface，origin 必須保留 Host | login/API/private 全部 bypass cache |
| api.kuanguard.com | KUANGUARD API gateway/Tunnel | 預設拒絕；明示 allowlist |
| admin.kuanguard.com | 私有 internal surface + Access | 核定 issuer/audience、MFA；不能掛到公開 Vercel alias |
| app.kuanguard.com | 既有商家來源產品 | 來源產品單獨設定／發布與驗收 |

`infra/gateway/public-api.conf` 允許 `/partner/*`，包含被後端嚴格驗證的 delegated aliases；直接 `/internal`、`/platform`、development login 不對外。API transport host 為 `api.kuanguard.com`，BFF 的簽章承載實際使用者入口。未簽章的任意 forwarding headers 不能作租戶判斷。

Partner public image 模板為 `infra/compose.partner.yml`，與 internal web 分開部署；不會自動 publish ports。Cloudflare for SaaS 須先核定產品方案、custom hostname/DCV、fallback origin 與證書成本，再設定 `CUSTOM_DOMAIN_TARGET`。

Edge policy：HTTPS redirect、HSTS（確認整體 domain/TLS 後）、WAF managed rules、login/lead/API 限速、Security Headers、Access 規則、無 secrets 的結構化 audit。正式 rate limiting 要由 edge/共用儲存補齊；目前 Python process-local limiter 不能單獨當多副本限流證據。

先在 KUANGUARD Staging 驗證精確 origins、session、redirect、TLS、兩 Partner 隔離與 static/private cache，再產生正式不可變發布收據。不得關閉安全測試或 release gate 來通過啟用。
