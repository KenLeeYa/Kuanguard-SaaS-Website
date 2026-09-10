# Parser 能力與資料口徑

版本 `kuanguard-parsers/1.0.0`，2026-09-10。所有範例均為合成資料，沒有執行來源程式、掃描資產或外部服務請求。

| 服務 | 可匯入格式 | 實際能力與限制 |
| --- | --- | --- |
| VA | Nessus CSV | 必要欄位 Plugin ID、Host、Risk、Name；讀取 Port、Protocol、Description、Solution、CVE、Plugin Output。UTF-8/BOM。finding 列不代表整個資產已測完。 |
| VA | `.nessus` | `NessusClientData_v2/Report/ReportHost/ReportItem`；保存沒有 finding 的 ReportHost；HOST_START 與 HOST_END 證明該主機批次完成，明示 scan-status 失敗優先。沒有完整時間證據保留 insufficient。 |
| WVA | `all.csv` | 明確欄位 Issue ID、URL、Severity、Name，加 Method、Parameter、Description、Solution、Evidence。不是任意廠商 CSV 猜測映射。 |
| WVA | XML 映射 profile | 只接受 `XmlReport schemaVersion="kuanguard-appscan-1"`。原生 HCL/IBM AppScan XML 尚缺授權真實 fixture 及版本相容性證據，回傳 UNSUPPORTED_APPSCAN_SCHEMA。productVersion 僅保存來源資訊，不自動啟用相容性。 |
| SHC | JSON | `kuanguard.shc/1`、checklist_version、checks。保留通過、不通過、不適用、未檢測、證據不足；通過或失敗缺預期值、觀測值、證據或 reviewer 時降為證據不足。完整 coverage 需另外宣告。 |
| PT | JSON | `kuanguard.pt/1`，包含授權 reference、方法、時段、停止條件及人工發現。未 reviewed 或沒有 reviewer 不得建立核定 snapshot。 |
| SOURCE | SARIF JSON | SARIF 2.1.0，tool.driver/rules/results/locations/partialFingerprints、來源版本資訊。明示 covered_paths 加成功 invocation 才認定完成。停用規則、排除路徑與失敗 invocation 阻止修復判定。 |

不接受 ZIP、原始碼壓縮包、HTML、可執行檔、Office 匯入或任意 Git URL。ProjectSetting.xlsx、SHC Excel、原生 AppScan 版本及 SCA/SBOM/Container/IaC 特定供應商格式尚未啟用，不應對客戶宣稱已支援。原生 Nessus 結構測試是解析器證據，不是掃描器/OEM 授權證據。

Informational/None 保留來源但排除 Critical/High/Medium/Low 四級統計；缺失或不可識別的風險為 Unknown。沒有來源 CVSS/CVE/CWE/修補版本時不補造。種類數依來源方法和來源弱點 ID；實例數加入資產、port/protocol、位置及 method/parameter；受影響資產數另外計算。IP 正規化，IPv6 顯示 port 時使用中括號，不猜未知 port。

WVA 以未遮罩位置的 SHA256 參與去重，公開位置遮罩敏感 query 值及 URL userinfo。SARIF 有穩定 fingerprint 時可以跨行號位移匹配；沒有 fingerprint 時保留各個 line/column 實例，不因同檔同規則誤刪發現。檔名移動無穩定證據時不得自動判修復。

預定範圍、完成、未測、失敗、證據不足分開保留；新增資產不擴大原 scope 分母。SHC 合格率分母為全部適用檢核，包含未檢測與證據不足，另列證據覆蓋率。已通過或不適用檢核不算四級弱點。

同批多來源可透過 `build_snapshot(..., context={additional_sources:[...], source_precedence:"csv"})` 使用 CSV 優先，保存每個 source_hash、來源獨有實例及 severity/title/description/solution 差異。只有明定 `first` 才改用第一來源。沒有全域 SSL Plugin 排除，沒有歷史統計常數。

複測狀態為 new、persistent、verified_remediated、reappeared、not_covered、indeterminate。缺少發現只有在原資產完成、原規則/路徑覆蓋、scope_confirmed、相同 method 及個別驗證 evidence/reviewer_id 均成立才可標已驗證修復。

輸入上限 10 MiB、20,000 findings、單欄 50,000 字元；API 可施加更嚴格限制。DTD/外部實體、active XML 節點、重複 JSON key、CSV 欄數錯誤及不支援 schema 均拒絕並清除部分輸出。描述與證據作文字輸出，不執行 HTML；CSV/XLSX 防公式注入。實測情境見 `backend/tests/test_parsers_reports.py`。
