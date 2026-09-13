# 官網產品入口與七語版本

2026-09-13 官網介紹更新後，字典共 598 個來源文字，較本次原始版本增加 110 個來源與 660 個目標翻譯。新增三項自有產品、八個合作方向、合作流程與 FAQ；StudyMesh 官網可連線但登入尚在啟用準備中。詳 [官網介紹與合作修改](WEBSITE_INTRODUCTION.md)。以下保留 2026-09-12 七語建置紀錄。

2026-09-12 更新範圍為公開官網，不包含產品後台、資料庫、付款或寄送服務的啟用。

## 產品入口

攤點通點餐介紹保留 KuanGuard 的品牌版型，新增專屬介紹區：主要入口為「了解攤點通」，旁列商家申請及既有帳號登入。外部服務名稱及網域清楚顯示；同一視窗導覽，使用者可自行開新分頁。

| 用途 | 正式目的地 |
| --- | --- |
| 攤點通官網 | https://qidaigo.com |
| 商家登入 | https://app.qidaigo.com/login |
| 商家申請 | https://docs.google.com/forms/d/e/1FAIpQLSf859kVKh77cjNjpS26HWNqFdN851UdOQ6htlJUc9pgBlBBLw/viewform |

目的地集中於 `apps/web/src/lib/product-links.ts`。既有 `/merchant/apply`、`/merchant`、`/login/merchant` 及七語版本均直接轉到對應服務，不轉送原網址的查詢資料。Google 表單網址已由攤點通正式官網核對；本次未送出表單或登入帳號。

一般 `/login` 是系統選擇頁。合作夥伴與企業資安的指定入口各自說明尚未開放，沒有虛構登入網址。美業從點餐適用產業移除，僅在產品總覽列為獨立規劃項目；舊 `/solutions/beauty` 永久轉至總覽的規劃區。

## 語言與官網基本功能

支援 `zh-TW`、`zh-CN`、`en`、`ja`、`ko`、`th`、`vi`。未指定語言的網址以 307 依 Cookie 或瀏覽器 Accept-Language 選擇，無符合語言時預設繁體中文。明確語言網址優先於 Cookie，手動選擇保留頁面、查詢及錨點。必要語言 Cookie 最長一年，HTTPS 下使用 Secure，設定 SameSite=Lax。

公開文字在 React render 與伺服器輸出時翻譯，不使用瀏覽器自動翻譯或第三方翻譯請求。共 488 個來源文字項目具備六種目標翻譯。`Localized` 僅處理顯示文字與文字屬性，不變更連結識別、表單欄位值或事件。非官網工作空間維持原有 SessionProvider 與功能。

每種語言使用固定網址、正確 html lang、獨立標題與描述、canonical、hreflang、Open Graph 語言及 sitemap。網站地圖包含 34 個頁面的 238 個語言網址。重複的舊隱私、條款及信任網址永久轉到對應公開頁，登入與未開放入口不收錄。

補上語言選單、手機選單 Escape 返回焦點、可見鍵盤焦點、減少動態效果、網站使用說明、正式 404 與返回首頁、品牌 favicon。政策說明按實際官網流程更新：聯絡表單組成 mailto，不儲存或自動寄信；商家申請由 Google 表單處理。沒有加入廣告或行銷追蹤程式。

公開訂單費用依 2026-09-12 攤點通官網核對，試算加入每月 NT$1,499 上限，設備、金流及其他費用另計。功能狀態仍使用既有公開快照，不因官網更新而啟用產品能力。

## 驗證與限制

- 21 項單元／路由／資料隔離測試與 TypeScript 檢查通過。
- Next.js 16.3.4 正式建置、standalone 啟動通過。
- `node apps/web/tests/website-language-smoke.mjs <base-url> <evidence-path>` 檢查 238 個 sitemap 頁面、語言優先順序、頁面標記、翻譯遺漏、入口、政策轉址及 API／後台封鎖。
- 本機正式建置的 238 個語言頁面及 14 個登入／指定平台頁面檢查通過，未發現英文、韓文、泰文、越文頁面混入未翻譯中文字。
- 瀏覽器工具三次因管理員安全政策無法驗證而拒絕存取本機網址，未繞過限制。因此本輪未完成瀏覽器視覺、手機操作、螢幕閱讀器或完整 WCAG 稽核，不宣稱取得無障礙或法律合規認證。

參考：[攤點通正式官網](https://qidaigo.com/zh-TW)、[Google 多語系網站指南](https://developers.google.com/search/docs/specialty/international/managing-multi-regional-sites)、[W3C WCAG 2.2 檢查項目](https://www.w3.org/WAI/WCAG22/quickref/)。Google 指南先由 AnySearch 擷取；W3C 擷取失敗後改查官方頁面。
