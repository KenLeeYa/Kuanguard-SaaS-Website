# 需求／驗收追溯

基準為 `implementation-spec.md` 的 CORE-01～14、ENH-01～09、QA-01～22，加上增量 UPD-01～08；未另取得完整 v1.1 prompt，不虛構 CORE-15～17 或 QA-23～32。狀態「本機通過」只指明示合成/隔離環境；「部分」必須列缺口，不能充當 production gate。

測試別名：`platform`=`backend/tests/test_platform.py`；`report`=`test_report_workflow.py`；`parser`=`test_parsers_reports.py`；`final`=`test_final_workflows.py`；`PM`=`test_project_operations.py`；`worker`=`test_worker_recovery.py`；`PG`=`test_postgres_runtime.py`；`ops`=`test_operations.py`；其餘檔案同目錄。執行收據見 `docs/evidence/api-tests.xml`、`live-uat.json`、`apps/web/evidence/` 與 `infra/evidence/`。

## CORE

| ID | 實作與證據 | 狀態／缺口 |
| --- | --- | --- |
| CORE-01 | 七服務 catalog/UI；五種 report workflow + campaign/LMS；live UAT | 本機七項可操作；正式 Gophish／影片／模板待啟用 |
| CORE-02 | assigned engineer 的 preview/commit/review/publish；report | 本機通過；實際到場資料／模板待核定 |
| CORE-03 | 無 customer raw upload；API reject；platform/前端 surface smoke | 本機通過 |
| CORE-04 | published projections、downloads、reply、retest、calendar；report | 本機通過；未開客戶 evidence upload |
| CORE-05 | SARIF import、review、retest rule evidence；parser/report | 本機通過；無客戶 source upload 或任意 Git fetch |
| CORE-06 | campaign_routes、worker、adapters；platform/final | 部分：真實 Gophish 核心／SMTP 未接，sandbox 明示 |
| CORE-07 | 原創文字課程、派課、server progress/grade/certificate；platform/live UAT | 部分：可售影片／字幕／正式教材待提供與上架 |
| CORE-08 | wallet lots/append-only ledger、獨立 entitlements；PG/PM | 本機通過；正式核定價目尚缺 |
| CORE-09 | 無密碼 schema/HTML form，候選與人類分類；platform/final | 本機通過；真實 provider 事件仍待接 |
| CORE-10 | 購點、campaign、training inputs 不需 project；platform | 本機通過；全新企業 IdP 驗證／邀請待啟用 |
| CORE-11 | draft/publication separation、project grant、learner restrictions | 本機通過，含跨企業下載拒絕 |
| CORE-12 | single approved immutable snapshot、checksum、dashboard統計；report/parser | 本機通過；AI provider 關閉 |
| CORE-13 | 官網詢價；有限服務 batch quota；PM | 本機通過；正式範圍／頻率／費用仍需合約核定 |
| CORE-14 | 官網到 PM／客戶結果／學習整合，人工覆核留 actor | 本機通過；不宣稱無人掃描 |

## ENH

| ID | 實作與證據 | 狀態／缺口 |
| --- | --- | --- |
| ENH-01 | 日曆／年度 project/batch/status/dashboard；project_execution 待辦依賴、時區、明示技能／人員／覆核者／工具容量及工時成本 | 本機執行與拒絕案例通過；正式假日／SLA與跨企業共用實體工具政策待核定 |
| ENH-02 | project comments、ticket messages/內部備註、個人通知、會議決議／待辦依賴；ops/drafts_tickets/project_execution | 本機可操作；外部通知 provider 待啟用 |
| ENH-03 | 平台 suspicious-mail report、reported event／risk metrics | 本機入口可用；無 Outlook/Gmail 已發布外掛 |
| ENH-04 | source-code 能力清單／SARIF、SCA/SBOM/Secrets 明示選配 | 僅範圍與現有 SARIF；未配置工具不稱支援掃描 |
| ENH-05 | SHC JSON 檢核、status/evidence/分母 | 本機原創樣本；正式雲端/M365基準／授權待補 |
| ENH-06 | PT/source 服務範圍文案、報價服務代碼 | 本機配置；人工程式審查依實際交付能力 |
| ENH-07 | questionnaires/answers/versions/inert evidence/ref review/due；ops | 本機通過；無直接購買／自動查驗證據主張 |
| ENH-08 | 服務能力清單與 disabled adapter | 保留選配，不列已開放商品 |
| ENH-09 | 信任／政策頁、真實 integration state、文檔 | 部分：正式合规條款與可分享權利證據待核定 |

## QA

| ID | 驗證 | 結論與尚缺項 |
| --- | --- | --- |
| QA-01 | platform、PG、portfolio、ops、report；互換 tenant/project/job/download/learner IDs | 本機通過；完整所有 export/filter 與正式 host 驗證尚缺 |
| QA-02 | customer import/sign/finalize 強制拒絕；CSV/XLSX role checks | 本機通過 |
| QA-03 | 七 packages、各自 batch/scope/acceptance；report、PM | 本機通過；一批交付不關年度 |
| QA-04 | 五服務 actual parser→review→worker→5 formats→publication→replies/retest | 本機合成通過；真實到場／正式模板缺口 |
| QA-05 | parser/final：資訊、未知、零 finding scope、CSV/Nessus、兩份Nessus、CSV更正 | 本機通過 |
| QA-06 | SHC insufficient、PT review、SARIF disabled/excluded/rule proof | 本機通過 |
| QA-07 | 30 sample artifacts／20頁 PDF 視覺檢查、structural hashes | 部分：正式核准字型／完整 DOCX/PPTX Office 逐頁渲染未過 |
| QA-08 | report 中更正 publication supersedes、原 PDF bytes 保留、quota 不重耗 | 本機通過 |
| QA-09 | PM scope/fee version/衝突/release；retest deadline；worker expiry；project_execution 資格/期限/容量/時區/舊槽位與 stale version | 本機明示合成政策通過；正式人員技能／設備資料待核定 |
| QA-10 | sandbox purchase→reserve→simulate→event review→remediation；原創課程完課 | 部分：指定信箱真實 Gophish/SMTP end-to-end 未驗證 |
| QA-11 | PG 30 concurrent /10 points；worker claim/recovery；idempotency | 本機通過；正式規模吞吐需再測 |
| QA-12 | unknown/cancel/late accepted/reconcile/expired lease；worker/final | 部分：真實 SMTP accepted-after-crash/bounce 回執待接 |
| QA-13 | HMAC、額度/幣別、亂序、duplicate、partial refund、chargeback | sandbox 通過；invoice provider 真實 retry 未啟用 |
| QA-14 | 首啟一次、取消/過期 release、重訓新cohort；platform/worker/learning_entitlements | 本機通過：年度內含／贈送／人工席次優先，無雙扣；到期/離職釋放未啟動授權，調部門與跨企業身分保留 |
| QA-15 | 無密碼、多次候選不超分母、人工判讀、learner denial | 本機通過；真實郵件設備辨識待 provider evidence |
| QA-16 | private download、hash、session/tenant checks；LMS過期重播 | 本機通過；R2/Stream 真實 token 與 bucket未驗證 |
| QA-17 | XML entity、ZIP/path/ratio、公式、HTML inert/模板hash、不執行repo | 本機通過；正式 malware provider/大檔隔離待啟用 |
| QA-18 | bounded tables/表單與HTTP contracts，CSS breakpoints；三流程server草稿/CAS/dirty提示/分頁匯出 | 邏輯測試已補；CUA 管理政策仍阻擋 viewport/keyboard/screenshots；大型資料與實際焦點尚需瀏覽器驗證 |
| QA-19 | 22 infra tests、57 publicsurface blocks、11private headers、read-only DNS清冊；草稿精確路徑 gateway allowlist | 未正式切換：zone完整匯出、DS/NS/TLS/Access實環境待啟用 |
| QA-20 | 舊/新獨立 DB+object restore、job claim recovery、grant expiry；lifecycle/PG 真實 scoped erasure、archive、未知阻擋及中斷接續 | 本機機制通過；正式保存/法律保留與backup淘汰 attestation、異地key recovery仍待核定／實測 |
| QA-21 | quote latest/expiry、contract、scope fee offer→confirm→apply stale checks | 本機通過；真實商務簽署/收款仍待核定 |
| QA-22 | 無project自助API、用途/expiry/FEFO、resume/cancel/unknown/late rules | 部分：新企業真實 IdP onboarding、provider late receipt仍待啟用 |

## UPD

| ID | 增量落地 | 證據／状态 |
| --- | --- | --- |
| UPD-01 | 共用既有 owner、Cloudflare Account、Vercel Team、Supabase Org | shared-saas-inventory；唯讀核實 |
| UPD-02 | 專用 DB/queue/ledger/config/product bindings、禁止既有其他 Project IDs | test_update_boundaries、portfolio、payment negative tests |
| UPD-03 | Vercel public/learner/customer + container admin/API/worker + dedicated Supabase target | 可審閱 infra/deployment-plan-v1.1.json；遠端未建置 |
| UPD-04 | Vercel DNS-only；admin Tunnel+Access+app auth | infra/Cloudflare plan tests、publicsurface negatives；正式 DNS待切 |
| UPD-05 | owner-only七 Portfolio sections、bounded read-only signed summary、TTL/revoke/null | test_portfolio.py + live UI HTTP；QIDAIGO未連線 |
| UPD-06 | KUANGUARD shared selfservice points，獨立於訂餐 | product/mapping/HMAC/finance口徑 tests |
| UPD-07 | 單一 actor 顯式多角色；contract policy不能隨意關閉 | platform/final policy tightening；same actor report live UAT |
| UPD-08 | 原資料／來源／樣本保留，0002～0010 additive；繼續原 Phase 2～9 | 舊/新backup、migration replay、UAT；未重建專案或清除既有資料；erasure僅測試新建可丟棄tenant |

正式 release 沒有通過；上列「部分」與外部啟用均保留，不以測試總數替代逐項 gate。
