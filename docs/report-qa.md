# 報告 QA 紀錄

日期 2026-09-10。v1.1 明示保留原報告字型、統計與複測口徑，本文件的有效既有證據繼續沿用，未因部署改版重跑無關報告。

`backend/tests/test_parsers_reports.py` 共 26 tests 通過，該檔與兩個實作檔的 Ruff 檢查通過。情境包括 malicious XML/ZIP/HTML/JSON/CSV、Informational/Unknown、去重與 IPv6、零 finding scope、CSV 優先差異、SHC 缺證據、PT 未覆核、SARIF 行號與不同 occurrence、規則停用、未覆蓋複測、個別修復證據、hash 與 immutable bundle、防公式注入。

| 合成樣本 | PDF 頁數 | 四級實例 | 主要驗證 |
| --- | --- | --- | --- |
| va_initial | 4 | 2 | 完成但無 finding 的資產；另一資產未測；資訊級不算 Low |
| wva_initial | 3 | 2 | Critical/Low，敏感 query 遮罩，另一網站失敗 |
| shc_initial | 4 | 1 | 通過1、失敗1、不適用1、證據不足1；分母3 |
| pt_initial | 3 | 1 | 授權 reference、人工覆核、前置條件與重現說明 |
| source_initial | 3 | 1 | SARIF 規則/行號，排除路徑仍未測 |
| va_retest | 3 | 1 | 已驗證修復、仍存在、無法判定分開 |

合計 30 份 DOCX/PDF/PPTX/XLSX/CSV、6 份 manifest 與6份snapshot。全部20頁 PDF 使用 bundled Poppler 在110dpi轉成 PNG，已逐頁檢視文字、表格、頁碼與追溯內容，沒有文字裁切或缺字。版面調整將孤立的 trace 欄位和風險標題分頁問題修正；較長資料可分頁延續。

`samples/reports/qa_final/verification.json` 記錄全部 artifact checksum、快照一致性、CSV重算風險、XLSX四級數字、無Excel公式、DOCX字型/PAGE/TOC結構、PPTX每頁快照識別、PDF文字與render頁數。也記錄 authoring runtime 的實際套件版本，服務安裝版本以 uv.lock 為準。

限制：DOCX/PPTX 只重新開啟及結構檢查，未在 Word/PowerPoint 或 LibreOffice 全頁渲染；bundled runtime 未提供 LibreOffice，未改用使用者桌面 Office。PDF是獨立排版，不可作為Office轉檔通過證明。正式核准模板、容器字型使用權與真實供應商匿名樣本仍缺少，所以 production_ready=false。不能將這20頁示範檢查擴張為1000+列或正式模板全頁QA已完成。

重新檢查命令（限相關檔案變更後）：

```powershell
.venv/Scripts/python.exe -m pytest backend/tests/test_parsers_reports.py -q
.venv/Scripts/python.exe samples/reports/verify_samples.py
```

樣本產製需用新的空目錄，避免改寫既有 bundle；執行 `samples/reports/generate_samples.py --output <new-directory>`。重新產製後必須再做對應的逐頁渲染檢查，不能沿用舊 PNG 作新版證據。
