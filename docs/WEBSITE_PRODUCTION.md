# KuanGuard 官網部署

最新正式版本：2026-09-13 官網介紹與合作更新，來源 `f4eb11f5583809da55fc3ecb4e387bd8cf19b5a8`，Production `dpl_46CLAFepgW8sQEizCGEkVNPeUjWN` READY。18 項 Preview、正式網域 238 個語系公開頁面與 14 個平台入口通過；DNS／產品後台設定未改。詳 [本次修改與驗證](WEBSITE_INTRODUCTION.md) 及 [發布收據](evidence/website-introduction-release-20260913.json)。

本次發布範圍為公開公司官網。Vercel 專案 `kuanguard-website`（`prj_uZG3hm4ALsnqj2wL3Qa9e85F7tvy`）位於既有 Team `team_MMfsiG94K9Zy3e6w7Ccc9xY4`，Root Directory 固定為 `apps/web`、Node.js 24。

Production 與 Preview 均設定 `KUANGUARD_WEBSITE_ONLY=true`。此模式只提供明示的公開頁面，關閉 API 轉送、internal rewrite、後台與工作空間。頁面不載入 session，也不連到本機或正式資料庫；既有 SaaS、provider、登入與資料遷移 release gate 保留。

公開聯絡／資安詢價使用 `ada76145@gmail.com`。表單僅產生 mailto，訪客必須在自己的郵件程式完成寄送；網站不保存內容，也不宣稱已送達。2026-09-12 起，商家申請改連到攤點通 Google 表單，商家登入直接前往 `https://app.qidaigo.com/login`。其他平台與課程仍說明尚未開放。

`apps/web/src/lib/website-commerce.json` 保留既有公開功能狀態與 charge_enabled=false；2026-09-12 對照攤點通正式官網更新價目參考為 `qidaigo-public-20260912`，新增每月訂單費用 NT$1,499 上限。此快照不代表付款、外送或其他平台已啟用。價格／功能修改需同步此公開快照及來源核定資訊。

正式網域為 `https://kuanguard.com`，`www.kuanguard.com` 永久轉址至主網域並保留 path/query。Cloudflare 使用 DNS only，記錄內容以此 Vercel 專案實際回覆為準。本次已從 GoDaddy 取得完整 DNS 匯出並逐筆核對後切換 nameserver；後續變更仍須重新 inspect、備份、核對 drift 與產生具體 plan。

驗證：`npm --prefix apps/web test`、`npm --prefix apps/web run typecheck`，以及帶 `KUANGUARD_WEBSITE_ONLY=true` 的 production build／HTTP smoke。七語版本使用 `node apps/web/tests/website-language-smoke.mjs <base-url> <evidence-path>`。Preview 驗證通過後才指派正式網域。部署證據另記錄實際 commit、deployment、DNS 與 HTTP 結果。[七語與產品入口說明](WEBSITE_LOCALIZATION.md)。

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

## 2026-09-13 七語與產品入口發布

正式官網已更新：[攤點通介紹頁](https://kuanguard.com/zh-TW/products/ordering)、[產品與平台](https://kuanguard.com/zh-TW/products)。支援繁中、簡中、英文、日文、韓文、泰文及越文，自動語言選擇與手動切換並存。

- 發布來源 `e09ab3c3e49532e4c222948585c7d3b3f1541308`；`apps/web` tree `f60753eb649fa2b7816483827d3828b8ecbed244`。
- Preview `dpl_36Cuq3Qzw5Amsvnyd5DRiyrWQ3VM` 通過 16 項遠端檢查。Vercel promote 依相同來源建立 Production `dpl_C9sMv2DSjgSC3EKZTAdXhyG98CQU`，狀態 READY；apex、www 及 Vercel 備用網域均指向新版本。
- [發布分支 CI](https://github.com/KenLeeYa/Kuanguard-SaaS-Website/actions/runs/34703954138) 與 [main CI](https://github.com/KenLeeYa/Kuanguard-SaaS-Website/actions/runs/34704288879) 的 api/web jobs 全部成功。21 項單元測試、TypeScript、正式 build 與本機 standalone 驗證通過。
- 使用本機正常 DNS 解析與有效 TLS 驗證，正式網域 238 個語系公開頁面、14 個登入／指定平台頁面、語言選擇、產品轉址、政策轉址及 API／後台封鎖均通過。www 308 保留語言路徑與查詢參數。
- Cloudflare 名稱伺服器仍為 `liv.ns.cloudflare.com` 與 `sri.ns.cloudflare.com`，本次沒有修改 DNS、資料庫、外部產品帳號或提交申請。Vercel 保護設定保留。
- 官網更新已合併回本工作區並推送 main。既有 36 個未提交檔案中，35 個逐檔 hash 不變；同檔的 report upload test 經保留與重新套用，剩餘使用者 diff 的正規化 SHA256 完全相同，備份仍保留。
- 瀏覽器工具三次因管理員安全政策驗證無法取得而拒絕存取本機頁面。因此未執行手機視覺、瀏覽器互動或完整無障礙稽核；HTTP 檢查不代替這些實測。

機器可讀紀錄：[發布收據](evidence/website-seven-locales-release-20260913.json)、[Preview](evidence/website-seven-locales-preview-20260913.json)、[正式網域](evidence/website-seven-locales-production-20260913.json)、[本機修改保留](evidence/website-local-work-preserved-20260913.json)。完整產品入口及語言維護方式見 [WEBSITE_LOCALIZATION.md](WEBSITE_LOCALIZATION.md)。
合併回本工作區後，包含既有 report upload test 的 22 項前端測試亦通過。新 Production deployment 在發布後查詢的最近 10 分鐘範圍內，Vercel runtime error records 為 0；此為當時快照，不代表持續監控。
