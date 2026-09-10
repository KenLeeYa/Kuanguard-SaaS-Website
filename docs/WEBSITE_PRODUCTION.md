# KuanGuard 官網部署

本次發布範圍為公開公司官網。Vercel 專案 `kuanguard-website`（`prj_uZG3hm4ALsnqj2wL3Qa9e85F7tvy`）位於既有 Team `team_MMfsiG94K9Zy3e6w7Ccc9xY4`，Root Directory 固定為 `apps/web`、Node.js 24。

Production 與 Preview 均設定 `KUANGUARD_WEBSITE_ONLY=true`。此模式只提供明示的公開頁面，關閉 API 轉送、internal rewrite、後台與工作空間。頁面不載入 session，也不連到本機或正式資料庫；既有 SaaS、provider、登入與資料遷移 release gate 保留。

公開聯絡／商家諮詢／資安詢價使用 `ada76145@gmail.com`。表單僅產生 mailto，訪客必須在自己的郵件程式完成寄送；網站不保存內容，也不宣稱已送達。平台登入與課程入口說明尚未開放。

`apps/web/src/lib/website-commerce.json` 是 2026-09-10 既有本機公開商品資訊的發布快照，保留公開價目版本 `merchant-website-20260910-v1`、功能狀態及 charge_enabled=false。它不代表付款、外送或正式平台已啟用。價格／功能修改需同步此公開快照及來源核定資訊。

正式網域為 `https://kuanguard.com`，`www.kuanguard.com` 永久轉址至主網域並保留 path/query。Cloudflare 使用 DNS only，記錄內容以此 Vercel 專案實際回覆為準。本次已從 GoDaddy 取得完整 DNS 匯出並逐筆核對後切換 nameserver；後續變更仍須重新 inspect、備份、核對 drift 與產生具體 plan。

驗證：`npm --prefix apps/web test`、`npm --prefix apps/web run typecheck`，以及帶 `KUANGUARD_WEBSITE_ONLY=true` 的 production build／HTTP smoke。Preview 驗證通過後才指派正式網域。部署證據另記錄實際 commit、deployment、DNS 與 HTTP 結果。

## 2026-09-10 發布結果

- 正式官網：[kuanguard.com](https://kuanguard.com)；DNS 快取傳播期間可使用 [Vercel 備用網址](https://kuanguard-website.vercel.app)。
- 正式 deployment：`dpl_5VMeeqa674LKMcM1W1PP8A4rw6iz`，狀態 `READY`，已 promote。
- 發布來源：`a76f4e563b214d35fc92e07fc878f2365c32bd42`，`apps/web` tree `45931b87861e12ad1ec410b0ba86954a13b09dc1`。
- [網站來源 CI](https://github.com/KenLeeYa/Kuanguard-SaaS-Website/actions/runs/34483514251) 與 [Cloudflare 工具修正 CI](https://github.com/KenLeeYa/Kuanguard-SaaS-Website/actions/runs/34492032092) 的 api/web jobs 全部成功。官網 16 項單元測試、本機 68 項與 Vercel 網址 67 項 HTTP 檢查通過；DNS 工具另有 25 項測試與 45 個 subtests 通過。
- 自訂網域 39 個公開頁面、67 項 HTTP 檢查及 www 308 path/query 轉址驗證通過。此輪自訂網域測試在該 Node process 使用公開 Cloudflare DoH 的真實解析結果，TLS 驗證保持啟用；沒有更動 hosts 檔或系統 DNS。部分 resolver 仍快取舊停放站，尚不宣稱全球傳播完成。沒有執行瀏覽器視覺或寄信測試。
- Vercel 的 apex／www domain config 均回覆 `misconfigured: false`，兩個 alias 均指向上述正式 deployment。Let's Encrypt 憑證涵蓋 apex／www，兩個 Vercel apex 入口的 TLSv1.3 憑證驗證均通過。HTTP 驗證後的 20 分鐘範圍沒有 Vercel runtime errors。
- 為配合 Next 16.3 的 Vercel adapter，僅在 Vercel 上使用平台預設輸出，本機仍保留 standalone；相關 [Next.js issue](https://github.com/vercel/next.js/issues/96646)。

## 網域接入結果

Cloudflare 帳號為 `b1c70202652cd3b77dfec70e5463785f`，專用 zone 為 `ecadb2ab2b13229381ca5c8ceebc8bdd`，方案 Free、狀態 active。GoDaddy 已於 2026-09-10 14:48 UTC（臺灣 22:48）接受 nameserver-only 更新，隨後 domain detail 與兩台 `.com` parent 均確認 `liv.ns.cloudflare.com`、`sri.ns.cloudflare.com`。

GoDaddy 完整原始匯出有 6 筆，原停放 A 與 www 已改接 Vercel，兩筆 apex NS 由 Cloudflare 管理；原 `_domainconnect` CNAME 與 `_dmarc` TXT 的內容／TTL 完整保留。新 zone 共 5 筆使用者 DNS 記錄，沒有原有 MX、CAA 或子域委派。切換前兩台 `.com` parent 的 DS 均為空；本次沒有移除既有 DNSSEC，Cloudflare DNSSEC 簽署尚未另行啟用。

下表為已套用且經 Vercel API 與兩台 Cloudflare 權威 NS 驗證的設定。可持續管理的宣告檔為 [`infra/cloudflare/website-production.json`](../infra/cloudflare/website-production.json)，每筆明設 `ownership_mode: comment` 以支援 Cloudflare Free；既有 tag 模式與所有漂移／回復檢查保留。

| 類型 | 名稱 | 內容 | Proxy | TTL |
| --- | --- | --- | --- | --- |
| A | @ | 216.150.1.1 | DNS only | 300 |
| A | @ | 216.150.16.1 | DNS only | 300 |
| CNAME | www | 795e44d125569cf2.vercel-dns-016.com. | DNS only | 300 |

完整原始匯出、逐筆計畫／journal、供應商回覆與 reconciliation 位於忽略提交的 `infra/cloudflare/private/website-cutover-20260910/`。再次 inspect 後的 application DNS plan 為零變更。不要把完整 TXT 匯出、API 金鑰或私人驗證資料提交到 repository。

Cloudflare DoH 已回覆新 apex A／NS；Google DoH 的 www CNAME 已更新，apex 仍有舊快取，本機 resolver 也曾回覆舊停放 IP。這是快取傳播狀態，無需重複修改名稱伺服器。後續可重查 DNS 與執行 `node apps/web/tests/website-smoke.mjs https://kuanguard.com`，確認該網路上的解析也已更新。

本工作區的官網程式碼與已部署 `apps/web` tree 相同，DNS 設定與接入工具已推送至 `origin/main`。Vercel 專案目前使用 CLI 部署；GitHub push 只觸發 CI，未設定自動 Production 部署。

機器可讀證據：[發布收據](evidence/website-production-20260910.json)、[網域切換與 HTTP 收據](evidence/website-domain-cutover-20260910.json)、[DNS 記錄清單](website-dns-records-20260910.json)。官方參考：[Cloudflare full setup](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/)、[Vercel custom domain](https://vercel.com/docs/domains/working-with-domains/add-a-domain)、[GoDaddy NS 更新 API](https://developer.godaddy.com/openapi/domains-v1.json)。
