# 問卷、通知與工單操作

此增量使用既有 `questionnaires`、`questionnaire_answers`、`notifications`、`tickets` 和稽核表，不新增 migration。問卷是供應商資料整理與人工文字覆核工具，不構成認證、弱點檢測或證據真偽驗證。

所有操作以有效 session 的目前 tenant 為界；忽略或代入其他 tenant 的行為不受支援。列表以 SQL count/offset/limit 分頁，`page>=1`、`1<=page_size<=100`，回傳 `{items,total,page,page_size}`。新增端點拒絕其他 query scope 參數。POST 共用 Origin、CSRF 和 Idempotency-Key 驗證。冪等紀錄只存操作識別，重放重新讀取目前授權資料。

| 使用者 | API | 行為 |
|---|---|---|
| customer_admin | GET/POST `/customer/questionnaires` | 本企業問卷列表／建立 |
| customer_admin | GET `/customer/questionnaires/{id}` | 本企業問卷與題目 |
| customer_admin | POST `/customer/questionnaires/{id}/answers/{answer_id}` | 文字作答與證據參照 |
| reviewer | GET `/internal/questionnaires`、`/{id}` | 明示 reviewer 角色的本企業覆核範圍 |
| reviewer | POST `/internal/questionnaires/{id}/answers/{answer_id}/review` | 覆核目前版本 |
| 任一已驗證使用者 | GET `/customer/notifications` | 自己的通知 |
| 同一通知使用者 | POST `/customer/notifications/{id}/read` | 首次已讀時間，重放不改時間 |
| 工單原建立者 | GET `/customer/tickets/{id}` | 自己的原始工單與目前狀態 |
| pm | GET `/internal/tickets`、`/{id}` | 本企業支援工單 |
| pm | POST `/internal/tickets/{id}/status` | 狀態異動與理由稽核 |

既有 GET/POST `/customer/tickets` 保留；不新增同 method/path 路由。`portfolio_owner` 本身不包含 questionnaire 或 ticket 存取權，仍須具備對應角色；問卷權限不延伸到專案報告。

建立問卷接受 `{title,supplier,due_at,questions}`。標題／供應商各 1–120 字；due_at 必須帶 timezone；1–100 題，每題 1–2000 字。期限用於提醒，不自動產生通過或認證。回傳 status 是 `open`、`in_review`、`reviewed`；detail 的 `answers` 最多 100 筆，空答案／參照回傳空字串。

作答接受 `{answer,evidence_reference,expected_revision}`：答案 1–10000 字，參照最多 2000 字。參照是惰性文字，不抓取 URL、讀取本機路徑、啟動檢測或接受檔案上傳。覆核接受 `{decision,reason,expected_revision}`，decision 是 `reviewed`、`needs_revision`、`insufficient_evidence`，reason 1–1000 字。缺答案或參照時不能標為 reviewed。`revision` 是回應提供的 64 字元 SHA256；變動後舊版本操作回 409。文字更新會把 review_status 重設為 unreviewed，原覆核者、理由、版本摘要保留於稽核；此表尚非完整答案歷史版本庫。

通知 item 與 read 回應為 `{id,title,text,created_at,read_at,is_read}`，其他使用者或租戶的 ID 回 404。通知標題與文字均應以純文字呈現。

工單狀態 payload 是 `{status,expected_status,reason}`；status 為 `open`、`in_progress`、`closed`，reason 1–1000 字。狀態更新使用比對後寫入，保留原始 ticket.text，理由以附加稽核紀錄保存，不出現在客戶 detail。這一版沒有對話回覆表，不能把狀態紀錄稱為客服已回覆，也不覆寫原文模擬回覆。

測試使用暫存 SQLite 與既有合成使用者，不寫入本機營運資料庫。涵蓋 tenant／使用者範圍、角色、版本衝突、資料不足、冪等重放、CSRF、分頁與檔案欄位拒絕。
