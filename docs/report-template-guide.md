# 報告模板與快照指南

目前提供可執行的開發報告引擎與合成樣本。正式核准模板、使用權與 Office 全頁渲染尚未完成，`generate_bundle` 明確拒絕 `synthetic=false`，不能將本機示範宣稱正式報告模板已驗收。

`parse_assessment` 產生預覽；工程師及覆核流程由 API 授權。`build_snapshot(parsed, context)` 產生深複製且可校驗的 payload，包括來源、parser/schema、scope、規則、模板、知識與翻譯版本、reviewer/time、統計與複測。必須在呼叫前將 DB finding id 放入 parsed.findings；建立後不得再修改任何 snapshot 欄位。`generate_bundle(snapshot, Path)` 會驗證 hash 與覆核欄位。

每個 bundle 同時包含 report.docx、report.pdf、summary.pptx、summary.xlsx、all.csv、manifest.json。CSV 是可重算明細，XLSX 另含統計、範圍與複測頁籤。文件顯示 scope、四級風險及 N/A、資訊級/未知、各發現、改善與 trace。SHC 保留符合狀態，PT 保留授權方法及重現資料，源碼保留規則與檔案行號。單一服務數字全部由相同 snapshot 取得。

每個 artifact 以 SHA256 與長度記錄於 manifest。產製使用獨立暫存目錄，全部完成且重開檢查後才寫出 manifest。重複呼叫相同目錄會驗證現存 checksum，不重新產製；不同 snapshot 或被修改的既有檔案直接拒絕。正式更正應建立新 report_version、bundle 與 publication 關聯，不能覆蓋舊版。

本機 Windows 已發現標楷體 `kaiu.ttf` 與 Times New Roman，DOCX 明示字型及 14pt 正文，PDF 使用相同本機字型。PPTX 明示微軟正黑體與 Times New Roman，風險頁 title 26pt、主要文字 24pt、補充18pt。其他環境缺字型時 native PDF 使用明示 fallback，QA 不得宣稱模板等同，字型容器散布權仍需確認。長段落可續頁，PPTX 長說明分頁而不截尾。

DOCX 有 PAGE 與 TOC 欄位，待正式 Office renderer 更新。PDF 由 ReportLab 獨立產生，**不是 Word/PPT 轉檔證據**。目前沒有核准固定模板可保留特定頁首、表格、欄高與固定段落；未有能力證據的要求列為 pending，不能假裝已完全套版。

正式啟用程序：提供有權使用的匿名模板與正確對照資料，完成模板錨點映射、字型與授權清冊，配置隔離 Office 轉檔 worker，逐頁驗證 TOC/頁碼/字型/表格/長內容及跨檔數字，再由覆核流程解除 production gate。更新模板版本須保存前後證據。

已檢查範例位於 `samples/reports/bundles_final`，QA 位於 `samples/reports/qa_final`。`bundles`、`bundles_checked` 是保留的本機版面迭代，已由樣本目錄的 .gitignore 排除，不列為交付證據。
