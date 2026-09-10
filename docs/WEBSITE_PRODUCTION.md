# KuanGuard 官網部署

本次發布範圍為公開公司官網。Vercel 專案 `kuanguard-website`（`prj_uZG3hm4ALsnqj2wL3Qa9e85F7tvy`）位於既有 Team `team_MMfsiG94K9Zy3e6w7Ccc9xY4`，Root Directory 固定為 `apps/web`、Node.js 24。

Production 與 Preview 均設定 `KUANGUARD_WEBSITE_ONLY=true`。此模式只提供明示的公開頁面，關閉 API 轉送、internal rewrite、後台與工作空間。頁面不載入 session，也不連到本機或正式資料庫；既有 SaaS、provider、登入與資料遷移 release gate 保留。

公開聯絡／商家諮詢／資安詢價使用 `ada76145@gmail.com`。表單僅產生 mailto，訪客必須在自己的郵件程式完成寄送；網站不保存內容，也不宣稱已送達。平台登入與課程入口說明尚未開放。

`apps/web/src/lib/website-commerce.json` 是 2026-09-10 既有本機公開商品資訊的發布快照，保留公開價目版本 `merchant-website-20260910-v1`、功能狀態及 charge_enabled=false。它不代表付款、外送或正式平台已啟用。價格／功能修改需同步此公開快照及來源核定資訊。

網域目標為 `https://kuanguard.com`，`www.kuanguard.com` 永久轉址至主網域並保留 path/query。Cloudflare 應使用 DNS only，記錄內容以此 Vercel 專案實際回覆為準。切換 nameserver 前，須先從 GoDaddy 取得完整 DNS 記錄並保留 MX/TXT/CAA/子域委派；本次沒有核對完整匯出時，不可宣稱完成 DNS 切換。

驗證：`npm --prefix apps/web test`、`npm --prefix apps/web run typecheck`，以及帶 `KUANGUARD_WEBSITE_ONLY=true` 的 production build／HTTP smoke。Preview 驗證通過後才指派正式網域。部署證據另記錄實際 commit、deployment、DNS 與 HTTP 結果。
