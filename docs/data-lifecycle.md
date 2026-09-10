# 草稿、匯出與企業退場

本機增量已實作；本次沒有停用或刪除既有企業。刪除測試只處理各測試自行建立的 disposable tenant。正式保存日數、法律保留、備份淘汰證據及資料責任人確認仍須核定，不能用本機收據替代。

## 操作草稿與客服

活動、派課、購點草稿存於伺服器，限定 tenant + actor + kind + new。每類只有一份，24 小時有效，worker 清除到期內容。只收明示基本欄位，拒絕名單、附件、證據、巢狀任意 JSON；瀏覽器沒有持久化敏感草稿。PUT 以 expected_version 比較，DELETE 也必須指定版本；其他視窗更新時停止自動覆寫。相同內容的回覆遺失可安全讀回新版。實際建立活動／派課／訂單仍使用業務 idempotency，不把草稿視為交易成功。

工單只供建立者及目前企業的 PM 讀取與回覆；內部備註不投影給客戶。關閉後不能新增訊息，需透過有版本檢查的狀態流程重新開啟。公開回覆產生個人通知，重播不重複通知；文字內容不抄入 audit。

## 授權匯出

`GET /customer/data-export` 依原角色／project grant 提供已發布的 projects、reports、findings，以及被授權的 orders、training、本人 campaigns/tickets；每次最多 200 筆，有 next_cursor。不同分頁是各自的查詢時間，不宣稱同一交易快照。客戶不能指定 raw imports、未發布結果、內部成本或他人範圍。

完整私有封存由 `scripts/tenant_data.py export` 執行，需客戶管理者已登入提交的 data_export request，使用與 runtime 同 host/port/database 的獨立 migration credentials。CLI 在 tenant transaction lock 下檢查沒有 running jobs，逐表輸出 JSONL、最小使用者識別資料及完整 tenant object 清冊；每表與物件有 checksum。session、OIDC state、短期草稿、operational jobs、idempotency replay cache、公司 Portfolio cache 與 bearer lookup hashes 不輸出。目的檔必須是 object store 以外的新 private path。壓縮檔完成前沒有 manifest 的檔案屬不完整封存，不能交付。

```powershell
.venv\Scripts\python.exe scripts/tenant_data.py export --tenant TENANT_UUID --request REQUEST_UUID --path .local/exports/customer-approved.zip
```

使用者身分不按相同 email 跨企業合併；完整封存只含這份 request 的企業，archive 不自動傳送給任何人。正式交付仍需核實收件者、加密及安全交付管道。

## 退場與實際刪除分開

1. 客戶管理者提出 tenant_offboard request 及理由。操作人須同時具有目前企業的 PM 與 finance 明示角色，可由同一真實 actor 兼任。
2. 產生 10 分鐘有效的 plan，顯示進行中 jobs、未知寄送、待啟動授權和未寄訊息。計畫 digest 綁定實際狀態；變動則重新預覽。
3. 明確確認才執行 offboard。running jobs 或 unknown/in_flight 寄送一律阻擋；未寄訊息、未啟動課程與未消耗服務額度釋放，停止未執行工作，撤銷客戶／學員 membership 與 session，凍結新用點，保留 ledger、已發布文件、證書和歷史。
4. `offboarding` 只允許具有 PM+finance 的員工讀取保留資料、結清帳務及處理 lifecycle；不允許繼續建立報告、派工、授權或購點。mutation 在取得 tenant lock 後重新檢查 session/membership，避免排隊中的舊授權寫入。
5. 資料責任人核對 legal hold 已解除、財務結清、全企業保存日數與真實備份到期證據，建立不可任意重複的 tenant_all 核定。核定是供後續 executor 使用的紀錄，並不代表已刪除資料。
6. 獨立 operator CLI 產生 erasure manifest；保存或備份期限未到、仍有保留額度、pending 付款/退款、未知寄送／running work 都會拒絕。執行要提供精確的 manifest digest，並再核對表資料／物件 hashes。manifest 任何變動都要重做計畫。

```powershell
.venv\Scripts\python.exe scripts/tenant_data.py plan-erasure --tenant TENANT_UUID --request REQUEST_UUID --path .local/erasure/reviewed-plan.json
# 僅對已核定、到期且已審閱的這份計畫執行；不是首次啟動或部署步驟。
.venv\Scripts\python.exe scripts/tenant_data.py execute-erasure --tenant TENANT_UUID --request REQUEST_UUID --path .local/erasure/reviewed-plan.json --confirm-digest REVIEWED_SHA256
```

資料庫刪除依實際 FK 順序、每張表以 tenant_id 篩選；immutable trigger 只在 privileged transaction 內暫停對應 trigger，交易完成前恢復。runtime role 無 erasure_receipts 或 DDL 權限。所有來源 rows、inbox mapping 與存取記錄清除後，沒有其他企業 membership 的使用者才匿名化；其他企業身分保留。

SQL 清除後保留最小匿名 tombstone／checksum receipt，接著只刪清冊中的精確檔案，不執行 recursive delete。若檔案步驟中斷，狀態為 objects_pending/erasing，可從同一 receipt 接續；出現不在清冊的新檔或 hash 改變時停止。原始備份由其已核定淘汰機制管理，本 executor 不接觸其他備份目錄。全域售前詢價保有獨立資料目的與保存政策，不因一個企業 ID 被刪就刪除其他商務資料。

驗證包含 SQLite 的拒絕／重試／中斷還原／其他企業身分保留，及專用 PostgreSQL 中新建 disposable tenant 的真實刪除、其他既有 project rows 不變、immutable triggers 仍啟用。正式跨站備份淘汰及法律政策尚未驗證。
