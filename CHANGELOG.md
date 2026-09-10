# Changelog

## 2026-09-10 — Corporate digital technology website

- 依最新指示將 KUANGUARD 改為數位科技公司主品牌，加入 `/products`、`/solutions` 與公司導覽；SaaS、Partner 平台與資安服務分項呈現。
- 原點餐首頁與暖白／綠色樣式保留於 `/products/ordering`，原功能、收費、產業與申請路徑保持可用。
- 公司主站採霧白、石墨藍、細網格與原創產品關係示意；更新關於我們、聯絡頁、metadata、canonical 與 sitemap。
- 參考 Vercel、Cloudflare、Linear 的官方資訊架構，保留產品聲明與正式啟用界線；不變更 API、資料庫或既有產品部署。

## 2026-09-10 — Merchant website / Partner platform increment

- 將公共網站定位為商家點餐與營運 SaaS，加入功能、五產業、可配置價格、Partner、分流登入與 lead 表單；新增 SEO、同源 BFF、responsive 與繁中介面。
- 透過 migration 0011 增加 22 tables，保留原 80 tables／811 rows、七服務、報告、錢包與原部署。以 product entry/pricing projection 對接既有商家產品，沒有複製其 backend。
- 加入 N-Partner 客戶歸屬、個人限時／專案委派、RBAC、FEFO immutable credit allocation、branding、custom domain、平台管理、features 與 audit。
- 配置三傑科技合成 Partner 及 PENDING custom hostname；中央 OIDC intent/state/PKCE/nonce 與 browser-bound 一次性交換，session 綁定 Host；HMAC 保護 Node BFF 原始 Host。
- 增加隔離、角色、並行分配、域名/CORS、OIDC／proxy 和 lifecycle 相容測試，以及真實 HTTP acceptance。P2 schema 保留停用，正式 provider/DNS/Production 待核定。
- 同步至使用者指定 GitHub repository；保留 base `96ec019` 與既有備份／映像；最新測試及部署狀態见 docs/TEST_REPORT.md、docs/DEPLOYMENT.md。

## 2026-09-10 — v1.1 continuation baseline (`96ec019`)

已完成七服務本機流程、durable report worker、learning rights、project execution、drafts/tickets、資料 lifecycle、Portfolio read-only integration、資源盤點與本機備份還原。原證據與凍結 migration 保留；正式共同 release gate 仍關閉。
