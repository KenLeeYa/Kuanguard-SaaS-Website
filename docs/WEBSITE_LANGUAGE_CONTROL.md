# 官網語系控制項

2026-09-13：依使用者提供的桌面與手機截圖，調整公開官網的語系呈現。

- 地球圖示、目前語言與下拉箭頭位於同一個圓角控制項內，整個範圍都可點選。沿用原生 select，手機使用系統提供的選擇介面，保留鍵盤操作及七種語言的原文名稱。
- 公司官網與商家介紹頁的頁首共用同一個語系控制項。1280px 以下，控制項與選單按鈕並排，選單關閉時仍可切換語言。520px 以下保留 K 品牌圖示，完整品牌首頁名稱仍供輔助技術讀取。
- 語系與選單控制項至少 44px 高。手機版語系文字為 16px。開啟導覽選單後焦點進入第一個連結，Escape 關閉選單並回到選單按鈕。
- 頁尾使用相同控制項，620px 以下靠左排列。既有瀏覽器語言判斷、手動選擇 Cookie、網址路徑／查詢／錨點保留邏輯未變。

修正原因：原先 label 繼承全域表單樣式的 `flex-direction: column`，使地球圖示排列在下拉框上方。現在使用獨立容器與置於控制項內的裝飾圖示，不更動其他表單樣式。

來源 commit：`e6762422f70e416e87782c8b6f7d9f4bf83ced4a`；`apps/web` tree：`e87d709feb15696eb697d05e22ee6e176948b7da`。

驗證：21 項既有測試、TypeScript 與 Production build 通過；[本機 HTTP 檢查](evidence/website-language-button-local-20260913.json)涵蓋 238 個七語公開頁面，總計 259 個頁面／語言檢查。[頁首控制項讀回](evidence/website-language-button-controls-20260913.json)確認七語名稱、輔助標籤及控制項位於可收合導覽之外。

瀏覽器工具因 Codex app-server 啟動路徑錯誤而無法使用，沒有完成自動化桌面／手機視覺與互動實測。HTTP 與程式檢查不等同實機畫面或無障礙認證。

正式發布：[kuanguard.com](https://kuanguard.com/zh-TW/products)，Vercel Production `dpl_4aH3mBhKTqywXDAAv2hrtNg9xDZy` 為 READY，apex、www 與備用 Vercel 網域均指向此版本。Preview `dpl_Dx5MMeamxSgPEKtaJz7FchLnQYCj` 的 18 項檢查通過，七語頁首另確認只有一個語系控制項。

[正式網域 HTTP 驗證](evidence/website-language-button-production-20260913.json)涵蓋 238 個七語頁面與 14 個平台入口，總計 259 個頁面／語言檢查；新控制項與樣式檔均已從正式站讀回。發布後最近 10 分鐘範圍內，Vercel runtime error records 為 0，此為查詢當下快照。

來源已合併回 main，原工作區 36 個未提交檔案的 SHA256 全部不變。本次未修改 DNS、資料庫、產品帳號或送出表單。[完整發布收據](evidence/website-language-button-release-20260913.json)。
