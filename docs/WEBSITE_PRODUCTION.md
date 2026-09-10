# KuanGuard 官網部署

本次發布範圍為公開公司官網。Vercel 專案 `kuanguard-website`（`prj_uZG3hm4ALsnqj2wL3Qa9e85F7tvy`）位於既有 Team `team_MMfsiG94K9Zy3e6w7Ccc9xY4`，Root Directory 固定為 `apps/web`、Node.js 24。

Production 與 Preview 均設定 `KUANGUARD_WEBSITE_ONLY=true`。此模式只提供明示的公開頁面，關閉 API 轉送、internal rewrite、後台與工作空間。頁面不載入 session，也不連到本機或正式資料庫；既有 SaaS、provider、登入與資料遷移 release gate 保留。

公開聯絡／商家諮詢／資安詢價使用 `ada76145@gmail.com`。表單僅產生 mailto，訪客必須在自己的郵件程式完成寄送；網站不保存內容，也不宣稱已送達。平台登入與課程入口說明尚未開放。

`apps/web/src/lib/website-commerce.json` 是 2026-09-10 既有本機公開商品資訊的發布快照，保留公開價目版本 `merchant-website-20260910-v1`、功能狀態及 charge_enabled=false。它不代表付款、外送或正式平台已啟用。價格／功能修改需同步此公開快照及來源核定資訊。

網域目標為 `https://kuanguard.com`，`www.kuanguard.com` 永久轉址至主網域並保留 path/query。Cloudflare 應使用 DNS only，記錄內容以此 Vercel 專案實際回覆為準。切換 nameserver 前，須先從 GoDaddy 取得完整 DNS 記錄並保留 MX/TXT/CAA/子域委派；本次沒有核對完整匯出時，不可宣稱完成 DNS 切換。

驗證：`npm --prefix apps/web test`、`npm --prefix apps/web run typecheck`，以及帶 `KUANGUARD_WEBSITE_ONLY=true` 的 production build／HTTP smoke。Preview 驗證通過後才指派正式網域。部署證據另記錄實際 commit、deployment、DNS 與 HTTP 結果。

## 2026-09-10 發布結果

- 可公開開啟：[KuanGuard 官網](https://kuanguard-website.vercel.app)。
- 正式 deployment：`dpl_5VMeeqa674LKMcM1W1PP8A4rw6iz`，狀態 `READY`，已 promote。
- 發布來源：`a76f4e563b214d35fc92e07fc878f2365c32bd42`，`apps/web` tree `45931b87861e12ad1ec410b0ba86954a13b09dc1`。
- [GitHub CI](https://github.com/KenLeeYa/Kuanguard-SaaS-Website/actions/runs/34483514251) 的 api/web jobs 全部成功。16 項單元測試、本機 68 項與正式站 67 項 HTTP 檢查通過，涵蓋 39 個公開頁面。沒有執行瀏覽器視覺或寄信測試。
- Vercel 已加入 `kuanguard.com` 與 `www.kuanguard.com`；www 設為 308 轉址。網站已發佈，但自訂網域 DNS 尚未切換。
- 為配合 Next 16.3 的 Vercel adapter，僅在 Vercel 上使用平台預設輸出，本機仍保留 standalone；相關 [Next.js issue](https://github.com/vercel/next.js/issues/96646)。

## 網域接入待辦

目前權威 DNS 仍為 GoDaddy 的 `ns37.domaincontrol.com`、`ns38.domaincontrol.com`。Cloudflare 帳號 `b1c70202652cd3b77dfec70e5463785f` 尚無可見的 kuanguard.com zone，新增請求被拒絕：缺 `com.cloudflare.api.account.zone.create` 權限。現有 `GODADDY_PAT` 對 domain detail 回覆 HTTP 401；瀏覽器工具也因 app-server 無法啟動而不能代操作後台。

可更新本機既有 Cloudflare／GoDaddy API 授權後接續，或由網域管理者在後台完成以下步驟。不要把金鑰貼到聊天或放入 repository。

1. 在 GoDaddy 匯出 kuanguard.com 的完整 DNS，確認郵件、TXT、CAA 及子域委派。
2. 在指定 Cloudflare 帳號加入 kuanguard.com，選 Free，匯入並逐筆核對原 DNS。
3. 將官網的 A／www 記錄更新為下表；其他用途記錄保留。這些值是本專案 Vercel API 本次回覆的第一順位設定。

| 類型 | 名稱 | 內容 | Proxy | TTL |
| --- | --- | --- | --- | --- |
| A | @ | 216.150.1.1 | DNS only | 300 |
| A | @ | 216.150.16.1 | DNS only | 300 |
| CNAME | www | 795e44d125569cf2.vercel-dns-016.com. | DNS only | 300 |

4. 核對 DNSSEC 狀態與完整記錄後，在 GoDaddy 將 nameserver 改成 Cloudflare **實際分配給 kuanguard.com** 的兩筆值。尚未取得這兩筆值，不可借用其他網域的 nameserver。
5. 待權威委派生效，重查 Vercel domain config、kuanguard.com HTTPS、www path/query 轉址，再執行正式網域 HTTP smoke。

機器可讀證據：[發布收據](evidence/website-production-20260910.json)、[DNS 記錄清單](website-dns-records-20260910.json)。DNS 準備方式參考 [Cloudflare full setup](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/) 與 [Vercel custom domain](https://vercel.com/docs/domains/working-with-domains/add-a-domain)。
