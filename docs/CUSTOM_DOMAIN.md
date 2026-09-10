# Custom domain 驗證與撤銷

API 以資料庫 `tenant_domains` 的完整 hostname 找 Partner，不使用模糊字串、前端 tenant ID 或任意 X-Forwarded-Host。Domain unique，拒絕 IP、port、scheme、路徑、無效 DNS labels，以及平台和既有 QIDAIGO 保留網域。

流程：`PENDING → VERIFYING → ACTIVE`；停用為 `DISABLED`。ACTIVE 必須同時具所有權驗證時間、有效 TLS、核定路由目的地，且 Partner 與 `custom_domain` flag 仍有效。

1. 在 Partner 網域頁登記完整 hostname，API 一次回傳隨機 TXT challenge；数据库只存 hash。
2. DNS 管理者設定 `_kuanguard-verification.<hostname>` TXT 與核定 CNAME。`CUSTOM_DOMAIN_TARGET` 留白時驗證回 503，不猜測可用 target。
3. 由平台維運核對 Cloudflare custom hostname、certificate/DCV 與 fallback origin，再按驗證。程式確認 TXT、精確 CNAME，解析到 public IPv4 後鎖定該 IP，以原 hostname 作 SNI/CA TLS 驗證，避免回連私網或 DNS rebinding。
4. 驗證完成前不接受 custom host 登入或帶憑證 CORS。停用後既有 host session 失效。
5. 遺失 challenge 時可「重發驗證值」；採 expected_version 防止覆寫。ACTIVE 必須先停用才能重發，舊 challenge 立即失效。

這個 API 驗證 ownership、routing 與 TLS，不會建立遠端 DNS 記錄或替第三方簽發證書。Cloudflare ownership 與 certificate validation 是分開狀態，需一起完成才可啟用。參考 [Cloudflare hostname validation](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/hostname-validation/)。

Branding／登入頁／API／報告及下載不可快取。只允許確定不含身份內容的靜態檔由 CDN 快取；不得 Cache Everything。Domain 轉移需先撤銷舊歸屬與 session，再由擁有者重新驗證，沒有 wildcard tenant routing。
