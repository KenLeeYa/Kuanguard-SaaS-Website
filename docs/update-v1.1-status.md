# v1.1 incremental update status

最新接續：官網樣式由另一工作區負責，此區完成資安 Phase 稽核與共用限流／維運彙總增量。原 Phase 0～9 並非未開始，但 Gophish／影片／provider／onboarding 等仍有工程，Phase 10～11 正式啟用未完成；[SECURITY_PHASE_STATUS](SECURITY_PHASE_STATUS.md) 明列 ENG-01～07 與 Partner P2。下方 U0～U5 為保留的歷史收據；本輪 89 項不同測試與 247 paths OpenAPI 通過，沒有重跑全部 Phase 或重送交易。

Checkpoint: 2026-09-10 Asia/Taipei. Source: `update-spec-v1.1.md`.

## Existing progress at U0 (historical checkpoint)

Branch `main`, initial repository has no commits yet. All current uncommitted files belong to this task:
main owns API/schema/wallet/LMS; web_ui owns Next UI; report_engine owns pure report functions and samples;
infrastructure owns scoped cloud tools and backup scripts. No production application was deployed.
Existing Compose PostgreSQL and Redis are healthy; initial schema and two-tenant synthetic seed are committed
DB transactions. Report tests (26) and infrastructure tests (16) passed; six synthetic report bundles and
20 visually inspected PDF pages exist. PostgreSQL and one synthetic object were restored into a separate
database, with all 65 public table row counts matching. These valid checks are retained.

Phase 1 foundation is present; Phases 2–9 core code is being integrated, not yet all accepted. Phase 10
has read-only DNS inventory and backup evidence; accounts and production services remain unactivated.
No in-flight real mail, payments, DNS write, production migration or remote deployment existed at checkpoint.

| Requirement | Decision and impact | Execution | Validation | Rollback | Remaining |
| --- | --- | --- | --- | --- | --- |
| UPD-01 | shared owner/account defaults | explicit resource inventory, no automatic product key reuse | account readback where available | configuration only | account IDs/authorization |
| UPD-02 | retain independent DB/queue/storage/ledger | product-bound settings and dedicated Compose project retained | tenant/product/pool tests | preserved DB and backup | dedicated remote projects |
| UPD-03 | change deployment adapters only | Vercel public UI; container admin/API/worker; Supabase PostgreSQL target | targeted route/config tests | per-surface previous deployment/config | host budget/region/projects |
| UPD-04 | managed DNS delta | DNS-only Vercel records; admin Tunnel+Access plan | negative route and managed-diff tests | per-record verified inverse only | full DNS export, account/zone/Tunnel |
| UPD-05 | add read-only portfolio | owner grant, summary adapters, scope/TTL/status/finance definitions | source mismatch/timeout/revoke tests | remove route/grant; no source data writes | QIDAIGO summary endpoint |
| UPD-06 | retain KUANGUARD shared wallet | product-scoped order mapping; separate accounting | wrong-product webhook rejects | append-only compensations | real merchant contracts |
| UPD-07 | configurable independent review | additive project policy migration; real owner actor with explicit roles | same actor allowed by default, policy still enforced | policy column retained; re-enable required policy | any contract-specific policy |
| UPD-08 | preserve current progress | no reset/clean/reseed/recreated DB | before/after migration and representative regression | separate restore database receipt | original unfinished core workflows |

The initial schema is not replaced. `0002_review_policy` is an additive migration with explicit defaults;
existing assignments, snapshots, ledger entries, import hashes and outbox records remain intact. There is
one authoritative business writer, FastAPI. No dual-write migration to Supabase is active.

Status: U0 checkpoint recorded; U1–U3 implementation in progress. Final validation and U5 continuation
receipts will be appended after actual checks; this document does not assert production migration or launch.

## U0–U4 receipt — 2026-09-10 (retained checkpoint)

U0–U4 的可執行本機差異已套用；U5 已接回原 Phase 2–9，而非停在更新文件。

- 保留原 API/UI、PostgreSQL/Redis、imports、samples、wallet ledger、已完成報告與第一份 DR backup；無 reset/clean、重新 scaffold 或跨產品部署。
- 共用 SaaS 管理範圍已由官方工具唯讀核對；Cloudflare token/account有效，KUANGUARD zone在可見清單仍空白；獨立 Supabase/Vercel Projects未建立，QIDAIGO與其他產品IDs明確排除。
- Portfolio七區、簽章／scope／TTL／撤銷／unknown狀態；Vercel public與container admin分面；單一actor明示多角色及合約獨立覆核政策已實作。
- 增量 migrations 0002–0006：review policy、portfolio projection、retest evidence、worker claim fencing、服務額度 ledger保護。沒有覆寫舊已發布報告。
- 原流程接續完成五類報告交付、CSV更正／多Nessus合併、複測與新版本，演練事件判讀／財務核對／補救派課、XLSX名單、有限服務額度、線上變更費用確認、問卷／通知／工單。
- 此檢查點 backend整合：157 tests +33 subtests通過、Ruff通過；前端 typecheck/4 tests/production build通過，57項 public internal-block cases及11 private header cases通過。最新總數見下方 U5。
- 真實loopback API + PostgreSQL合成UAT成功，5種檢測25個artifact可下載，原創文字課程以真實elapsed time完成測驗與證書。證據 `docs/evidence/live-uat.json`；沒有實寄／真實扣款。
- 最新容器source binding、獨立DB/object還原以 `infra/evidence` 最後收據為準；原65tables檢查點繼續保留。

正式 Phase10–11 仍受資源／預算／完整DNS來源、IdP、Gophish/SMTP、商店／影片／私有物件、模板教材等啟用條件限制；原需求中尚未完成的進階功能逐項列 `requirements-traceability.md`，不宣稱完整平台已遷移或上線。瀏覽器驗證被管理政策阻擋，沒有繞過或虛構截圖。進一步啟用使用同一專案與資料，從目前收據接續。

## U5 原工作接續完成收據 — 2026-09-10

接續原 Phase 2–3、7–9 的待辦，而非重新執行 Phase：

- 三個流程的24小時伺服器草稿、版本衝突與離頁提示；工單對話、客戶回覆和內部備註隔離。
- 有限年度內含／贈送／人工席次；優先使用有效權益、取消／過期釋放、學員調部門及離職不影響其他租戶身分。
- 待辦依賴／會議決議、明示派工资格／交通緩衝／工具容量、估計與實際工時成本；建立專案可連結有效合約，毛利採合約與已登錄成本且保留未知狀態。
- 授權資料匯出、客戶退場申請與雙角色審核、即時撤銷後重新鑑權；精確清冊 erasure executor 支援中斷接續。刪除測試僅用本輪新增的可丟棄 tenant，原企業 A/B 與報告保留。匯出排除 live campaign bearer lookup、jobs 與認證資料。
- 僅新增0007～0010 migrations；沒有重新 seed、重建專案或重送原已完成交易。

最新驗證：214 tests＋45 subtests、Ruff、158 paths OpenAPI、前端 typecheck／10 tests／production build 均通過。新增5組真實 loopback HTTP checks 使用現有 PostgreSQL；原七服務 UAT 收據保留。三個容器來源／runtime/HTTP 檢查見 `infra/evidence/final-increment-images-20260910.json`。

最後一份獨立 DB/object 還原：80 tables／811 rows／36 objects（1,165,681 bytes）逐筆摘要相符，0001～0010 revisions保留，前兩份備份驗證未變。收據 `infra/evidence/backup-restore-complete-20260910.json`；manifest `94ab88f754ab524a9b11151169d275db2ed5b3a0a476b1d6515e74233ccf1abd`。

更新後 native API/worker 已啟動，3180 以已建置的 local surface 運行；DB/queue 與所有既有資料保留。CUA browser policy 仍阻擋實際 viewport/keyboard 驗證。狀態保持 **LOCAL_SYNTHETIC_READY / PRODUCTION_BLOCKED**；正式啟用只依集中清單補齊必要資料，不再逐 Phase 重做。
