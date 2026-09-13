# KUANGUARD 官網介紹與合作諮詢

2026-09-13 依 `Kuanguard_Website_Introduction_Codex_Prompt.md` v2.0 修改既有 kuanguard.com 官網。需求檔 SHA256：`C4838843457FD3CFD1B1528AC8A9285B06FF7C0CF3DFA037600C6FA7C706B130`。

## 公開頁面

- 首頁 `/`：數位產品與系統合作主視覺、三項自有產品、八個合作領域、四種合作方式、未來入口願景、四步合作流程、六題 FAQ 與資安／Partner 入口。
- `/products`：攤點通、美業工作室系統與 StudyMesh 分別標示狀態，另保留企業資安與 Partner 介紹。舊 `#beauty` 錨點有效，StudyMesh 使用 `#studymesh`。
- `/solutions`：食、美、衣、住、行、育樂、醫療、學術的合作方向。領域出現不代表已有廠商合作或完成介接。
- `/partners`：合作方式、願景、流程與 FAQ；原 Partner 平台介紹放在 `#partner-platform`，`/partner/login` 的既有連結與行為保留。
- `/about`：更新品牌定位與產品狀態，不添加未核實的公司登記名稱、地址、年份或統編。
- `/contact?kind=partner`：沿用既有 mailto 表單與欄位，合作訊息提示包括公司／系統名稱、領域、官網與構想。主旨為 `KUANGUARD｜系統合作諮詢`；須由訪客在自己的郵件程式確認寄出。

首頁使用靜態產品介紹與狀態清單，沒有商家搜尋、名錄、地圖、假統計、合作 logo 或模擬平台。FAQ 使用原生 details／summary；圖片僅沿用現有品牌識別，使用既有圖示庫。

## 產品依據與待確認事項

2026-09-13 先使用 AnySearch 擷取官方頁面核對，未登入、申請或寄出訊息：

| 項目 | 官網顯示狀態 | 依據與界線 |
| --- | --- | --- |
| 攤點通 | 開放申請評估 | [官方介紹](https://qidaigo.com/zh-TW) 提供 QR 點餐、POS、KDS 與多據點介紹，採申請與個別評估；不新增已開放訂位等未核實宣稱。 |
| 攤點通入口 | 沿用原設定 | [商家登入](https://app.qidaigo.com/login) 與 [Google 申請表單](https://docs.google.com/forms/d/e/1FAIpQLSf859kVKh77cjNjpS26HWNqFdN851UdOQ6htlJUc9pgBlBBLw/viewform) 已核對，網址未改。 |
| 美業工作室系統 | 規劃中 | 使用者已確認為獨立、尚未上線產品；沒有新增名稱、官網、登入或試用網址。 |
| StudyMesh | 開發中 | [官方介紹](https://getstudymesh.com) 已公開；[登入頁](https://getstudymesh.com/login) 明示 Google 登入仍在啟用設定中。只提供官網介紹，不提供登入或試用按鈕。正式開放狀態待產品團隊確認。 |
| 企業資安與 Partner | 保留既有入口 | 資安服務頁面、Partner 登入行為與既有資料隔離保留；不啟用尚未開放的公開平台。 |
| 聯絡 | 沿用確認信箱 | `ada76145@gmail.com`；不變更寄送流程或宣稱郵件已送達。 |

共同入口、商家搜尋及曝光都屬合作規劃。訂閱資格與公開同意分開確認，以獲授權的公開商家資訊與服務連結為基礎，不要求顧客名單、病歷或私人學習資料。

## 維護位置

- `apps/web/src/lib/website-introduction.ts`：三項產品、八個領域、合作文案、流程與 FAQ 的靜態設定。
- `apps/web/src/components/corporate-site.tsx`：沿用品牌的官網版型、產品清單與合作區塊。
- `apps/web/src/lib/product-links.ts`：核實產品網址；未開放的平台登入維持 null。
- `apps/web/src/lib/translations.json`：新增 110 個來源文字及 660 個目標翻譯，合計 598 個文字項目；七語設定不變。
- `apps/web/src/lib/commerce.ts`、`src/app/layout.tsx`、`src/app/[[...path]]/page.tsx`：標題、描述、路由與結構化資料描述。
- `apps/web/src/components/commerce-site.tsx`：關於介紹與原 Partner 內容的嵌入呈現。
- `apps/web/src/components/website-contact.tsx`：僅補充既有訊息欄位提示。
- `apps/web/src/app/website.css`：產品、合作、FAQ、閱讀字級及響應式排版。

## 驗證

- 既有 21 項單元／路由測試、TypeScript 與 Next.js 16.3.4 正式建置通過。
- 本機 development 與 standalone production 的 238 個 sitemap 語系頁面、14 個平台入口、共 259 項頁面／語言檢查通過。
- HTTP 驗證涵蓋三項產品、八個領域、六題 FAQ、合作規劃標示、StudyMesh 無啟用登入、Partner／資安入口、同頁錨點、七語翻譯、canonical／hreflang、舊轉址及 API／後台封鎖。
- 新首頁錨點為合法的 `/<locale>#products`；既有測試調整為檢查 URL pathname，避免將保留語系的錨點連結誤判為失敗。
- 沒有獨立 lint script；使用既有測試、型別與建置工具，未新增測試框架或套件。
- 瀏覽器工具於本輪啟動時失敗：`failed to start codex app-server`，`系統找不到指定的路徑 (os error 3)`。因此手機／桌面截圖、實際操作、縮放與完整無障礙視覺稽核尚未完成；HTTP 與 CSS 檢查不等同瀏覽器實測。沒有改用其他自動化方式繞過工具限制。

[本機正式建置 HTTP 紀錄](evidence/website-introduction-local-20260913.json)。正式發布結果另記於本次發布收據。

## 範圍確認

沒有新增或修改後端、資料庫、migration、API、webhook、會員、訂閱、付款、分潤、商家搜尋或管理平台。價格與公開功能快照保持不變。沒有修改 qidaigo.com／getstudymesh.com、三傑整合、DNS、憑證、使用者權限或追蹤 SDK。

開始前主工作區有 36 個未提交檔案，屬既有報告工具修改；本次在相同 repository 的乾淨 worktree 完成官網修改，再合併並比對原檔 hash。未找到本次要求取代的 Life Service 入口平台實作；既有報告工具與資安平台保留。
