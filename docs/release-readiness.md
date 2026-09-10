# Release readiness

狀態：**LOCAL_SYNTHETIC_READY / PRODUCTION_BLOCKED**。已套用 v1.1，並接續完成原 Phase 2～9 的主要本機資料流及 Phase 10～11 的本機建置／還原／UAT。沒有新建其他產品、搬遷正式資料或對外上線。

## 實際完成

- 官網七服務、詢價入庫、CRM、版本報價／合約、七工作包、有限服務額度、排程、範圍／費用確認、客戶單批驗收。
- 五類內部匯入到五格式 immutable report bundle、授權下載、reply/retest/correction。CSV/Nessus 優先及多份 Nessus 合併有 regression；核定政策與發布版本重新查核。
- 點數預留／消耗／到期／退款、並發與 idempotency，unknown 接受需證據核對；候選判讀→補救派課；原創文字課程有真正 server progress、grade、certificate。
- 專用資源隔離、Portfolio 七區、QIDAIGO bounded read-only 契約與未連線狀態；個人通知、問卷版本覆核、工單狀態。
- 原工作接續：三流程短期 server 草稿與版本衝突、工單對話／內部備註、有限內含／贈送／人工課程席次、學員調部門／離職、專案待辦依賴／決議、派工資格／工具容量和工時成本；授權匯出、退場及精確清冊 erase executor。
- 正式 surface 的 local production build、API/worker/web 容器配置；原與新增 DB/object 備份還原收據。

## 驗證收據

| 項目 | 收據／實際範圍 |
| --- | --- |
| Backend / parser / wallet / RBAC / worker / infra | `docs/evidence/api-tests.xml`：214 passed、45 subtests；Ruff 通過；OpenAPI 158 paths 同步 |
| Frontend type/build/10 tests | `docs/evidence/web-build-final.json`；source/config SHA-256 與正式建置通過 |
| 原 HTTP contracts | `apps/web/evidence/http-smoke.json` |
| 新操作 HTTP contracts | `apps/web/evidence/operations-smoke.json`，7組 |
| 原工作接續 HTTP contracts | `docs/evidence/frontend-increment-smoke.json`，5組：草稿／席次／工單／專案／退場；6個新增私有頁的 no-store/noindex |
| Host/alias/encoded/internal route blocks | `apps/web/evidence/public-surface-smoke.json`，57組拒絕＋11私有頁 headers |
| 真實 loopback API+PG synthetic UAT | `docs/evidence/live-uat.json`；5種檢測25個檔案、sandbox 活動、無調整時間的學習與證書 |
| 既有報告樣本 | `samples/reports/qa_final/verification.json`；30份樣本、20頁 PDF人工視覺檢查 |
| Image/runtime/source binding | `infra/evidence/final-increment-images-20260910.json`；API/worker 各60個來源、web 57個來源全部相符；無網路隔離容器檢查通過 |
| DB/object restore | `infra/evidence/backup-restore-complete-20260910.json` 與逐表 comparison；獨立還原成功 |
| Git source／secret exclusion | `docs/evidence/source-review-final.json`；三個映像來源與 staged blobs 位元相符，秘密／runtime資料未提交；原始SQL與更新需求檔保留原空白 |

最後一次還原已核對 80 tables、811 rows、36 objects（1,165,681 bytes），逐表筆數及 PostgreSQL JSON digest、來源/備份/還原 object hashes 全相同，保留0001～0010 revisions。目標為新建的獨立 `kuanguard_restore_20260910_complete`；原65表與67表兩份備份 hash 再核對未變。備份前持有 tenant locks、確認 running jobs=0，僅暫停已驗證的本專案 API/worker；完成後以新程式啟動，DB/queue/web 保留。後續本機操作會新增 rows，此數量代表備份檢查點。

UAT 20次本機 dashboard 請求 P50約70ms、P95約97ms；此為少量合成資料、單機和本機連線，不代表生產 SLA 或容量證明。真實寄信 0、真實扣款 0。CI workflow 已準備，未 push／遠端執行。

Python 測試有兩項第三方 TestClient/httpx/AnyIO deprecation warnings，未遮蔽且未造成失敗；未為消除警告而臨時改動已鎖定的依賴。

## 尚不能上線

1. 專用 Supabase/Vercel Projects、容器主機／地區／預算、KUANGUARD zone 範圍與完整原權威匯出、NS/DS/TLS/Access/WAF 實際切換。
2. 真實 IdP／MFA／邀請與停權、正式 tenant onboarding；Gophish source+adapter、SMTP／事件回執、商店／發票、private R2／Stream 必須實接及驗證。目前 disabled/sandbox 不能靠 env flag 改名為正式成功。
3. 合法核定 templates／公司資料／可售教材字幕題庫、原生 AppScan 樣本與格式；完整 Office 每頁字型／長內容／TOC／版面 QA。
4. 正式服務假日／SLA／技能與工具清冊、全企業保存與法律保留／備份淘汰 attestation、完整正式監控及 distributed rate limits 仍需核定與實環境驗證；不能套用本機合成政策。內含課程授權、資料退場、依賴／成本與草稿已接續實作，證據見 traceability。
5. CUA 管理政策拒絕 browser automation；未繞過，390/768/1440、完整鍵盤／焦點／錄影尚無證據。

## 下一次啟用

先依 `activation-checklist.md` 集中取得必要帳號／budget／provider／權利資料；再以目前 source/image receipts 做有限差異部署。正式 DB 只可選已核對的 KUANGUARD 專用 Project，先 isolated migration+restore+七服務 sandbox UAT，再以新 Plan 和明確核定的 DNS diff 切換。QIDAIGO 來源 patch 僅為提案，未經來源維護流程不可自動合併、部署或更動費率／出單。

若還原程式版本，保留新增欄位與 append-only 歷史、先 drain worker；未知外部接受必須先對帳，禁止直接清空 jobs/ledger。正式 gate 每项須有新環境實測，不能沿用本機合成 receipt。
