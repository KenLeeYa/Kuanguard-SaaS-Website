# KUANGUARD design system

狀態：已實作本機前端；2026-09-10。v1.1 增量沿用原視覺與四種入口，新增公司總覽。

## 品牌與資訊原則

品牌文字為 KUANGUARD，副標「企業資安服務平台」。官網使用原創服務文案、CSS 工作台示意與線性圖示，未使用客戶 Logo、認證、歷史營收或成效數字。首頁產品預覽標示「示範資料」，長度條是服務交付路徑示意，不代表真實改善率。

官網採海軍藍 hero、白色服務區與青綠行動色。應用採白底、深色側欄、可水平捲動表格與精簡狀態標籤。依台灣繁體中文、Asia/Taipei 時區及實際授權顯示內容。

| Token | 值 | 用途 |
| --- | --- | --- |
| brand | #0B1F33 | 官網 hero 與品牌 |
| primary | #0F766E | 行動、連結與焦點內容 |
| surface | #FFFFFF | 表單、卡片與表格 |
| canvas | #F4F7FA | 工作空間背景 |
| text | #172B4D | 主要文字 |
| muted | #52657B | 次要文字 |
| border | #DCE4ED | 分隔與輪廓 |

中文優先使用裝置已有 Noto Sans TC，再使用 Microsoft JhengHei/system fallback。未向第三方字型服務發送請求，未將未授權字型打包。英文/數字使用已安裝 Inter 或系統字型。Lucide 圖示以 npm lockfile 固定版本。

## 可及性與互動

- 已實作 skip link、語言標示、表單 label、fieldset/legend、可見 focus、狀態文字、嚴重度文字加圖示、aria-live 錯誤、reduced-motion 與鍵盤原生控制。
- 表格一次請求 20 筆（API 以實際 page_size 回傳），搜尋明示「目前頁面」，有欄位選擇與受控水平捲動，沒有誤導的全資料全選。大量資料的分頁上限由 API 控制。
- 所有 mutation 使用 CSRF token 與 Origin；冪等 key 在同 payload 重試時維持不變，成功後才建立下一個操作 key。重複點擊以 in-flight guard 阻擋。
- 購點、派課、活動與發布先顯示確認內容。部分文字表單在關閉或重新載入頁面前使用 beforeunload 提示；完整站內導航草稿保護、跨裝置草稿與自動儲存衝突處理仍待實作，未將私有證據持久存於 localStorage。
- 企業切換透過重新登入重新取得 session；載入期間卸載舊 workspace 與資料請求，先清空舊範圍再載入新身份。不存在任意 tenant ID 輸入。
- Loading / empty / error / no-permission / expired / retry / partial CSV/XLSX import 均有內容。沒有檢測結果時顯示未檢測說明，不產生安全總分。
- 問卷回覆／覆核使用 revision 避免覆寫他人更新；工單與變更確認檢查原始狀態／版本。郵件 unknown 對帳先預覽供應商結果、時間與原因，確認後才處理原預留，沒有重寄操作。
- V1.1 公司總覽只在 portfolio_owner 授權下顯示。未連線、過時、撤銷或不完整來源不顯示數值；不將 QIDAIGO GMV、KUANGUARD 合約或點數耗用相加為營收。

## 響應式

已加入 1320、1080、800、500 CSS breakpoints；設計目標為 390 / 768 / 1440。手機改為單欄表單與卡片，側欄切換為可收合選單；工程師結果使用表格內部捲動。

實際 390 / 768 / 1440 瀏覽器畫面、鍵盤完整流程、螢幕閱讀器與全站 WCAG 2.2 AA 尚未驗證。CUA 開啟本機 URL 時被阻擋：管理政策檢查無法完成，工具明確禁止改走間接方式繞過；因此沒有捏造 screenshot 或視覺 pass。

## 驗證

`npm run test` 的行為測試包含部署 surface fail-closed；對 body/muted/action/hero/error 六組實際 token 配色計算 WCAG 相對亮度，均達 normal text 4.5:1。這不代表所有裝飾、細字、hover 或聚焦狀態均通過完整 AA 評估。

`npm run typecheck` 與 `npm run build` 通過。HTTP smoke 驗證公開 SSR HTML、四入口路由標頭、API rewrite、角色隔離、真實詢價入後台與 portfolio 未連線口徑。詳見 `apps/web/evidence/`。

Next dev 由框架設定 `Cache-Control: no-cache, must-revalidate`；正式 build 另測 no-store，兩者證據不混用。Next 16.3.4 / React 19.3.0 於 2026-09-10 以 AnySearch 官方 Next blog 與 npm registry 驗證 stable，固定套件及 lockfile；TypeScript 固定經驗證的 5.9.3。
