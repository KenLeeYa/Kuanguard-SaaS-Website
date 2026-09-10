# 專案、到場作業與交付手冊

## PM 與客戶

公開詢價建立真實 lead。PM 提出有到期日的 quote，每次修訂產生新版本；有授權的 customer contact 明示接受最新版本後建立 contract。專案包含七 work packages，单次委託也可有自身專案；自助購点／演練／派課不需 project ID。

先核定有限 `batch` entitlement，再建立服務批次。排程必須使用有效 engineer/reviewer 角色、未來 start/end 和設備，所有時間保存 UTC、UI 呈現 Asia/Taipei。人員／設備衝突包含 30 分鐘緩衝。真實人員技能證照、工具容量與完整依賴甘特目前仍需營運設定，開發 roster 不代表正式資格認定。

客戶範圍／改期申請先由 PM 提供帶版本的追加金額，再由客戶確認，最後 PM 套用。舊版本與未確認不能套用。scope 追加保留原 `scope_version`；已匯入批次必須另開追加批次，不改寫既有檢測範圍。改期重新檢查衝突，保留 original_start_at 和 schedule_history。追加費用的確認不是收款成功。

## 五種檢測

1. 指派工程師完成授權範圍的到場／內部檢測，於內部匯入合法結果。沒有客戶原始檔上傳、任意 repo fetch 或遠端自動掃描。
2. 檢查 preview 的 errors、warnings、scope 與來源 SHA-256，成功才 commit。原始內容放 private quarantine。支援格式見 parser-capabilities。
3. 指派 reviewer 核定；一般單人 actor 可持明示角色，獨立覆核合約仍拒絕自核。VA 最近提交的 CSV 為整份優先來源，保留各來源差異；其他來源 occurrence 重複採最近提交資料。介面／報告保留 selection policy。
4. 建立 report job；worker 產出五種格式和 checksum。內部先用 draft download 覆核，核准後 publication 才使客戶可見。檔案缺失／hash 改變／過期核定／政策不符一律拒絕發布。
5. 客戶以已授權的 publication 查結果、下載、文字回覆。客戶說已修補只建立待驗證紀錄，不修改漏洞狀態。
6. 客戶申請複測，PM 核准獨立 retest batch、有限額度與截止日；原資產方法、規則執行、scope coverage 和 reviewer 個別驗證俱足才能判 verified_remediated。缺項則 persistent/not_covered/indeterminate。
7. 更正先 `reopen`，原發行版繼續可追溯；新資料或既有來源 `submit-review` 後重新核定並產新 snapshot/bundle/publication。獨立覆核政策在產製與發布再檢查。

同一批次驗收只建立 batch acceptance，年度 project 保持 active。補救學習、付款、專案履約、發現修復為不同狀態，不互相冒充完成。

## Jobs 與 recovery

worker 每次 claim 有獨立 token、5 分鐘 lease、每 60 秒續租，結果回寫仍需 matching claim。每次報告寫獨立輸出目錄，無法覆蓋已完成 bundle。失敗只記 error code，人工查看來源／模板後再重試；不要改已發布快照來消除失敗。排程暫停不消耗 retry 次數；已知未寄過期／終止釋放預留；未知接受保留給財務核對。
