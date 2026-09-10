# 資安系統 Phase 稽核與接續狀態

查核日期：2026-09-10（Asia/Taipei）。本輪基準 `c59b01898677d1597b699cf381de5fa30ae2930f`。

依最新指示，官網樣式由另一工作區負責；本工作區接續資安後端、租戶與 Partner 權限、報告處理、演練、LMS、帳務及維運架構。保留現有前端和資料，沒有重新 scaffold、重跑全部 Phase 或執行正式部署。

**結論：原 Phase 0～9 均已有實作；Phase 4、5、7、8、9 尚有功能或驗收缺口，Phase 10、11 只完成本機與可審閱部署準備，正式部署及啟用未執行。不能把「有資料表／停用 adapter」視為已完成整合。** Phase 6 原定的金流 sandbox 已有證據，但正式支付／發票仍需接續工程與外部驗收。Partner 更新的 P2 完整功能尚未執行。

## Prompt 來源

Downloads 中三個原檔與 repo 保存版本逐一比對 SHA-256，內容相同；本輪不修改原 prompt。

| 原檔 | 專案保存版本 | 追蹤範圍 |
| --- | --- | --- |
| kuanguard_codex_prompt.md | [implementation-spec.md](implementation-spec.md) | §19 的 Phase 0～11、CORE-01～14、ENH-01～09、QA-01～22 |
| kuanguard_codex_update_v1_1.md | [update-spec-v1.1.md](update-spec-v1.1.md) | U0～U5、UPD-01～08；增量套用並接回七服務 |
| Kuanguard_SaaS_Website_Partner_Portal_Update_Prompt.md | [partner-platform-update-spec.md](partner-platform-update-spec.md) | 保留原七服務、Partner 隔離／委派、P0／P1／P2 |

未收到另一份完整 v1.1 規格，不推造其他 CORE／QA 編號。官網視覺的後續責任依最新工作區分工，不回頭重做商家官網。

## 原 Phase 0～11

「本機已實作」指現有程式及合成驗證，不代表真實供應商或 Production 已通過。完整需求仍以 [requirements-traceability.md](requirements-traceability.md) 為準。

| Phase | 已保留的實作／證據 | 尚未完成及下一個完成條件 |
| --- | --- | --- |
| 0：盤點與架構 | ADR、ERD、來源權利、三版規格、產品隔離與歷史 DNS inspect | 正式模板／教材權利及新部署時的 DNS 現況需核定／重取；不重跑整個盤點 |
| 1：系統基礎 | FastAPI／Next／PostgreSQL、FORCE RLS、個人 membership／grant、session、BFF HMAC、OIDC broker、CI；本輪新增 Redis 共用限流 | 真實 IdP／MFA 與部署入口驗收；OIDC contract 通過不等於外部登入已驗收 |
| 2：詢價與商務 | 七服務目錄、詢價入後台、CRM、報價版本／確認、合約、年度權益 | 正式公司／條款／價目；企業首次驗證與邀請閉環仍見 ENG-05。官網樣式由另一工作區執行 |
| 3：專案履約 | 七工作包／多批次、有限服務額度、排程與衝突、變更費用／驗收、待辦依賴／會議／派工资格／工具容量／工時成本 | 正式技能／設備／假日與 SLA 政策；日曆與互動排程的瀏覽器驗收待完成 |
| 4：VA／WVA | CSV／Nessus／映射 XML、snapshot、DOCX／PDF／PPTX／XLSX／CSV、覆核／更正／複測 | 公司核准模板／字型、真實初複測樣本與完整 Office 逐頁 QA；原生 AppScan 未支援，不能改名宣稱支援 |
| 5：SHC／PT／SOURCE | JSON／SARIF 匯入、覆核／發布、證據不足與未覆蓋規則判斷、改善與複測 | 正式工具與樣本驗收、核准模板；SCA／SBOM／Secrets／雲端基準只是明示選配，不是已接掃描器 |
| 6：帳本與 sandbox | append-only ledger、FEFO、預留／消耗／到期、並行與冪等、signed sandbox 支付／退款／對帳 | 本 Phase 的 sandbox 已實作；正式商店支付／發票 adapter、退款／chargeback 回執與 provider retry 仍見 ENG-03 |
| 7：社交工程演練 | 名單／活動／排程、sandbox outbox、接受／拒絕／未知、事件判讀、取消／補救派課；無密碼收集 | **Gophish adapter 仍只會拒絕執行**；租戶引擎綁定、實寄與 provider 事件／中斷對帳未完成，見 ENG-01 |
| 8：LMS | 文字課程、派課／授權席次、首次啟動扣點、伺服器學習時間／測驗／證明、補救派課 | **video-token 固定 503**；Stream 簽章／教材字幕與內容上架版本流程仍未完成，見 ENG-02 |
| 9：客戶與营運 | 授權結果／報告下載、回覆／複測、工單對話／內部備註、問卷／通知、草稿、資料匯出／退場 | 正式 onboarding／邀請及外部通知；大型資料／瀏覽器驗收與保存政策核定。Partner P2 另列，不能當成已完成選配 |
| 10：部署與維運 | 專用容器／DB／worker、DNS plan/verify/rollback、私有下載、本機 backup/restore；本輪新增可執行租戶維運彙總 | **正式 Projects／主機、DNS Apply／NS／TLS／Access 未完成**；R2、監控排程／告警、異地加密 DR 尚未實接，見 ENG-04、07 |
| 11：共同驗收與啟用 | 七服務合成本機 UAT、migration／restore 演練、既有 GitHub CI 收據 | **正式七服務 E2E／UAT／切換與 launch gate 未通過**；需前述工程、供應商、權利與環境驗收共同完成 |

## 尚需工程的缺口

以下區分程式缺口和外部條件；不是全部只差 credentials，也沒有將 Phase 5／7／8 改成未來功能。

| ID／原 Phase | 程式現況與接續工程 | 必要外部條件／驗收 |
| --- | --- | --- |
| ENG-01／7 | `adapters.GophishAdapter.dispatch/reconcile` 拋出未啟用；worker 只處理 `sandbox_mail`。需實作既有 Gophish 版本的 tenant cell／模板／sender 綁定、dispatch、事件與 unknown reconciliation | ACT-09／10：合法來源版本、獨立引擎、寄送規範及授權測試信箱；真實 accepted-after-crash／bounce／取消／late event，不能盲目重送 |
| ENG-02／8 | `learning_routes.video_token` 固定拒絕；現有 `/internal/courses` 只有查詢。需教材／題庫／字幕版本上架、受限影片 token 和有效期檢查 | ACT-06／12：Stream 帳號及權利、核准教材與課程政策；重播不重扣、撤銷／到期無 token |
| ENG-03／6、10 | `billing_routes` 目前是 sandbox merchant／webhook，invoice 是停用狀態。需綁定選定支付／發票 provider 的 idempotent inbox/outbox、退款及失敗重試 | ACT-08：供應商／商店與稅務決策；簽章、金額／幣別、亂序、chargeback、重放及發票 retry |
| ENG-04／10 | `r2_*` 設定欄位存在，但報告仍寫本機 objects 並由 API 代理下載。需 R2 私有 storage adapter、完整 objects/version inventory 與備份恢復 | ACT-06／14：專用 bucket、key、保存／RPO/RTO 核定；跨租戶與無登入取檔拒絕、實際異地還原 |
| ENG-05／1、2、9 | OIDC 已有 state／PKCE／nonce／issuer／audience 與現有 membership 綁定；新企業建立／驗證、邀請／加入申請、正式通知閉環仍需工程 | ACT-07／13：IdP、營運主體與管理權驗證政策；不得以相同 email domain 自動加權 |
| ENG-06／3、4、10 | 報告 lease／fencing／重試已有；目前 worker 依全域 oldest queued、最多 100 candidates 取件，沒有已驗證的租戶公平排隊／完整 render 時間與記憶體量測 | 先核定代表負載／公平性與 timeout 契約，再做排程增量；不能只以容器 mem_limit 當成完整公平排程證據 |
| ENG-07／10 | 本輪完成 jobs／unknown mail／payment-grant 彙總與 Redis 健康，但外部 scheduler／on-call 去重／告警回復／TLS-DNS-cost collectors 尚未建置 | ACT-15：監控目的地與閾值；授權故障演練及通知抵達證據。未傳送任何對外訊息 |

建議接續依賴順序：ENG-01／02／04 的 provider contract 與 ENG-05 身分開通 → 工具／模板與正式資料驗收 → ENG-06／07 維運與隔離負載 → Phase 10 Staging → Phase 11 七服務共同驗收。支付／發票選定後接 ENG-03。各項維持現有專案、schema revision 與 ledger，不重建。

## v1.1 與 Partner 增量

- U0～U3 的檢查點、產品邊界與 Portfolio 本機程式已保留；QIDAIGO source connector 仍未連線。
- U4 的本機測試／部署差異已有證據，正式 Cloudflare／Vercel／Supabase 切換未執行。
- U5 已接回原工作；本輪補上 Phase 1／10 共用限流及可執行監控，仍接續上述工程清單。
- Partner P0／P1 的本機權限、customer ownership／個人 delegation、credits、project integration、feature flags 與 audit 已實作；三傑正式 domain／TLS／IdP 仍待驗收。
- **Partner P2 未完成完整功能**：commission 計算／結算／撥款、enterprise OIDC/SAML federation、advanced CRM／analytics、referral、onboarding automation。部分只有停用 schema；中央 OIDC broker 不等於已完成每租戶 enterprise SSO。

## 本輪實作與驗證

- `rate_limits.py`：Redis 原子 60 秒滑動窗口，產品／環境／操作種類分區；連線中斷回 503、不退回 memory；429 保留 trace ID 與 Retry-After。memory 僅本機選項，鎖定並行操作，最多 4,096 個 active keys。
- `runtime_operations.py`：`GET /internal/operations/health`，目前 tenant 的 PM／platform admin 才可讀；拒絕 project delegation、額外 query scope、公開／Partner alias。只回 aggregate，不回報告、收件人、訂单／job IDs。
- 原有 102 表／0011 Partner migration、既有報告物件與備份保留；本輪沒有 schema migration 或交易回放。
- 89 項不同測試通過：88 項受影響回歸與新增代理邊界測試；[回歸收據](evidence/security-architecture-tests-20260910.xml)、[14 項 runtime 專項](evidence/security-runtime-tests-20260910.xml) 的 13 項重疊不重複加總。20 項[真實 HTTP 檢查](evidence/security-runtime-http-20260910.json)經 Node BFF／本機 API／PostgreSQL／Redis 通過，含偽造 forwarded IP 不改變 quota。API 契約 [OpenAPI](openapi.json) 為 247 paths。
- API／worker 共用映像重新建置，以 non-root、network-none、無來源 DB／objects mount 完成 [smoke 與來源綁定](../infra/evidence/security-api-image-smoke-20260910.json)。本機 native API 已更新，worker／網站程序保留；未部署到外部雲端。
- [狀態與來源收據](evidence/security-phase-audit-20260910.json) 保存 prompt SHA、只讀 DB／migration 回讀、既有物件數量及實作 hash。HTTP 檢查僅新增／撤銷合成登入 session 和短期限流 keys，不修改原業務交易。
- 過去 250 tests／45 subtests、102 tables restore 及七服務 UAT 為保留的歷史證據，見 [TEST_REPORT](TEST_REPORT.md)。本輪未為改 MD 重跑全部 Phase、完整七服務交易或建立新備份。

狀態仍為 **LOCAL_SYNTHETIC_READY / PRODUCTION_BLOCKED**。正式 gate 不因新增檢查或文件標示而放行。外部必要輸入見 [activation-checklist](activation-checklist.md)，本文件的 ENG 清單用於追蹤仍需實作的工作。
