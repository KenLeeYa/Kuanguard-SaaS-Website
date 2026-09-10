# LMS 有限席次授權

QA-14 的年度方案內含、贈送與人工核發已接到既有派課、首次啟動、取消及到期流程。三種來源使用獨立的有限席次帳本；沒有適用席次時才使用共用點數錢包。這是示範課程的授權機制，課程完課證明不代表資安專業認證。

## 授權與帳本規則

- `training_entitlements` 保存核發人、理由、來源參考、課程、可選期別、數量與起訖效期。`annual_included` 必須關聯同租戶有效合約；`gift`、`manual` 也必須有核發依據及正整數數量。日期必須包含時區。
- 一席等於一筆 enrollment 的首次啟動授權。這是累計可啟動的有限席次，並非無限課程或可循環使用的同時在線席次。課程與期別必須適用，並先用最早到期的權益。
- `training_entitlement_ledger` 只附加 `reserve`、`consume`、`release`。每個 enrollment 每種分錄都有唯一業務鍵；一筆預留只能耗用或釋放一次。核發資料與帳本均不可改寫或刪除。
- 派課先檢查同課程、同學員、同期別的既有 enrollment。已存在的授權沿用原資料，不另扣點或占席；已取消的期別不能重建，新年度重訓必須使用新期別。之後核發新權益不會改寫既有點數授權來源。
- 新派課先清理到期或學員已停用的未啟動預留，再選席次。有席次時 `reservation_id=null`，完全不呼叫 wallet reserve/consume；無席次才沿用點數流程。課程授權為 14 天且不得超過席次來源效期。
- 首次啟動才 consume。重複請求及有效期內續看不重扣；啟動狀態更新失敗時，consume 與狀態更新在同一資料庫交易回滾。
- 未啟動取消、到期或離職會 release；來源效期已過時，釋放不會讓席次重新可用。已啟動或完課的席次仍計入 consumed，不退回席次或點數。舊成績、enrollment 與證書保留。
- PostgreSQL 的租戶 advisory transaction lock 將席次檢查、分錄、enrollment 與 idempotency 一起序列化。權益表無 UPDATE 權限，故不對權益表使用 `SELECT FOR UPDATE`。來源參考及理由是惰性文字，系統不抓取 URL 或上傳資料。

帳本可重算：`reserved = reserve - consume - release`，`consumed = consume`；有效期內 `available = quantity - reserved - consumed`。尚未生效或已到期時對外 `available=0`，保留原始帳本統計供追溯。

## API

所有路由沿用 `learning_routes.router`，由既有 API 註冊載入。不得從客戶傳入 tenant 或任意擴大資料範圍。所有 POST 使用現有 session、Origin、CSRF 與 Idempotency-Key 驗證。

| 方法與路徑 | 明示角色 | 內容 |
|---|---|---|
| GET `/customer/training/entitlements` | `training_manager` | 當前租戶席次、來源、效期及統計 |
| GET `/internal/training/entitlements` | `pm` | 同租戶核發紀錄 |
| POST `/internal/training/entitlements` | `pm` | 核發有限席次，回傳目前統計的單筆權益 |
| GET `/internal/training/courses` | `pm` | 可用課程，僅 id/title/version/points/status |
| GET `/internal/training/contracts` | `pm` | 同租戶 active 合約，僅 id/title/version |
| GET `/customer/training/assignment-preview` | `training_manager` | 課程、學員、期別的來源預覽，不預留或扣帳 |
| GET `/customer/training/learners` | `training_manager` 或 `customer_admin` | 沿用現有有效學員名單；不賦予派課以外的角色 |
| POST `/customer/training/learners/{learner_id}/deactivate` | `customer_admin` | 停用當前租戶 learner 身分並釋放未啟動預留 |
| POST `/customer/training/learners/{learner_id}/department` | `customer_admin` | 以舊部門比對更新當前租戶 learner 的部門 |

四個清單端點皆採資料庫 `page>=1`、`page_size=1..100` 分頁，回傳 `{items,total,page,page_size}`。額外範圍參數會拒絕。權益 item 包含原核發欄位與 `course_title/reserved/consumed/released/available/status/unit/policy_version`；`status` 為 scheduled、active 或 expired，`unit=enrollment_seat`。

核發 POST：

```json
{
  "course_id": "已存在的課程 ID",
  "source": "annual_included",
  "quantity": 20,
  "starts_at": "2026-09-10T00:00:00+08:00",
  "expires_at": "2027-09-10T00:00:00+08:00",
  "cohort": "2026",
  "contract_id": "同租戶有效合約 ID",
  "source_reference": "已核定合約的訓練席次條款參考",
  "reason": "年度方案內含 20 席"
}
```

`source` 限 annual_included/gift/manual；`quantity` 為 1..100000 的整數；`cohort` 可省略或為 null，代表不限制期別；`contract_id` 對年度內含必填。`source_reference` 1..200 字、`reason` 1..1000 字。數量或期別不符不會擴張授權。

預覽 query 為 `course_id/learner_id/cohort`。回傳 `{existing_enrollment_id,source,entitlement_id,unit,quantity,expires_at,preview:true,notice}`。有 `existing_enrollment_id` 時沿用該筆授權；無值時是預計新增需求。預覽不保留額度，實際派課交易重新核對當下來源。既有派課及 learner detail 回傳新增 `authorization`，含實際來源、entitlement_id、單位、數量及到期時間；不以預覽結果冒充已取得授權。

學員停用 body 為 `{reason}`（1..1000 字），調部門 body 為 `{department,expected_department,reason}`。新部門 1..120 字；舊部門 0..120 字，必須原樣回傳名單內容作 CAS 比對，保留舊資料的空白。比對失敗回 `409 DEPARTMENT_CHANGED`；已停用 learner 不接受調部門或新派課。`training_manager` 只有名單與派課權限，沒有明示 `customer_admin` 就不能停用或變更會員部門。

兩個管理操作回傳 `{id,learner_id,name,email,department,active,scope:"current_tenant_learner_membership"}`；停用另含 `released_enrollment_ids`。Idempotency replay 返回目前身分狀態，不用舊部門值覆蓋新狀態。停用只更新當前租戶的 learner membership，保留 global user、其他角色與其他企業會員；釋放未啟動預留與會員停用是同一交易。Audit 保留完整理由與部門前後值，課程、成績及證書不刪除。

## 停用、背景處理與保存

`release_unstarted_for_learner(conn, tenant_id, learner_id, reason)` 供 offboarding executor 在同一租戶交易中呼叫，回傳已取消的 enrollment ID 清單。只處理 `assigned`，不釋放已啟動/完課資料，也不把使用者的 `users.active` 全域停用。

Worker 的 `expire_training()` 同時處理課程預留到期與已失效的當前租戶 learner membership。其他角色或另一個租戶的 learner membership 不會維持原租戶的 learner 存取權；所有 learner 路由會重新核對有效角色。證書與舊紀錄仍保留，已停用學員不能再讀取其個人內容。

Worker claim 在租戶交易內重新確認 tenant active；失效租戶的待辦 job 取消，既未送出的郵件釋放，unknown 郵件仍保留預留。租戶日後重新啟用也不會自動重跑取消的 job。相同週期清理已到期的 24 小時 form draft，不把草稿 payload 寫到 audit。

## 加入既有資料庫

專用 module 提供 `training_metadata` 與 `TRAINING_TABLES`；不修改原 enrollment schema。由 additive `0008_training_rights` migration 呼叫 `training_metadata.create_all(conn)`，對兩表設定 FORCE RLS 與 tenant policy、immutable trigger 及 UPDATE/DELETE 撤權。測試 fixture 另外建立 training_metadata，正式執行權限交由主 migration 流程管理。

本增量未重建資料庫、未回填或刪除舊 enrollment/證書，也未改初始 schema SQL。

針對性驗證命令：

```powershell
uv run pytest backend/tests/test_learning_entitlements.py backend/tests/test_worker_recovery.py backend/tests/test_platform.py::test_lms_charge_once_progress_grading_and_certificate_privacy backend/tests/test_platform.py::test_lms_cancel_before_start_releases backend/tests/test_platform.py::test_start_replay_rechecks_current_course_expiry -q
```

案例涵蓋三種席次來源、滿額轉點數、取消再利用、最早到期/課程/期別/租戶邊界、過期及尚未生效權益、未啟動 release、已啟動不釋放、learner 停用、舊年度證書、新年度 enrollment、重試及故障交易回滾。Worker 案例保留 claim token/lease 復原驗證，不產生 PDF 或執行寄信。

2026-09-10 驗證：19 個新增案例、3 個原 LMS 回歸，以及 24 個 worker 復原案例通過；範圍內 Ruff 檢查通過。最後的派課到期邊界修改後，重新執行 19+3 個相關案例，共 22 passed；未重跑無變更的 worker 渲染 mock 案例。執行期間僅有兩項現存測試依賴 deprecation warning。

學員管理追加驗證：同檔增加離職、調部門 CAS、角色/租戶/CSRF/idempotency 負向案例，合計 24 passed；既有證書保存案例改用實際停用 API 驗證。此追加未修改 worker 或資料庫 schema。
