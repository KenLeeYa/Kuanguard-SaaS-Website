# 身分、資料安全與保存

## 可見性

| 身分 | 可用範圍 | 明確限制 |
| --- | --- | --- |
| 未登入 | 官網、課程 preview、匿名證書有效性、教育文字頁 | 無私有報告、付費課程內容、企業資料；教育頁無密碼欄位 |
| customer contact | 明示 project grant 的已發布結果、報告、時程、文字回覆與確認 | 無原始 evidence／未發布 finding／內部成本／工程師匯入 |
| campaign/training manager | 自己的群組活動／本企業派課與成效 | 不能任意改 tenant；候選點擊不自動認定人類 |
| billing manager | 企業 wallet／sandbox 訂單 | 不能人工更改 ledger；未知寄送由明示 finance 角色核對 |
| learner | 自己的有效 enrollment、進度、測驗與證明 | 無企業 wallet／報告；重播 start 仍重查有效期 |
| engineer/reviewer | 已指派且有 project grant 的來源／核定與交付 | 需實際角色和指派；一般 owner 不隱含 evidence 權限 |
| PM／finance | 目前受信 tenant 的履約／帳務及對應操作 | 權限不跨產品；配額／退款留 actor、版本、理由 |
| portfolio owner | 授權彙總、口徑與健康狀態 | 不取得 QIDAIGO DB／raw orders／admin key，不跨產品寫入 |

正式 identity 以 issuer + subject 對 server membership；不以同 Email 自動合併租戶或角色。Session 為高熵 opaque token 的 server-side hash，HttpOnly/host-only/SameSite cookie；正式才 Secure。本機 profile 僅 development/test；production 設定目前直接拒絕啟動。CSRF token、允許 Origin 與 idempotency key 保護 mutation。

## 已實測控制

- PostgreSQL runtime `kuanguard` 非 owner／superuser／BYPASSRLS；FORCE RLS、composite tenant FK、transaction-local tenant scope、connection pool commit/exception 後 scope 清除。
- append-only points/service ledger、audit、snapshot/publication。30 個併發請求競爭 10 點，只能有 10 次成功消耗，不負餘額。
- 公開部署模式在本機 production runtime 拒絕 admin path、Host alias、編碼路徑和 internal API；private routes 回 no-store/noindex。外部 Access 必須驗 JWT 簽章／issuer／audience／expiry，另有 app auth。
- Parser 使用 defused XML、大小／列數限制、明確 schema，來源當作 inert text；未下載或執行任意 repo。XLSX 不解壓到檔案系統，拒絕穿越、炸彈、加密、公式、巨集和外部關聯；報告 CSV/XLSX 防公式注入。
- Private download 每次重查 tenant/project/publication 與 checksum；無公開 object 靜態路由。學員停權／到期重新查核，不從舊 idempotency receipt 取得受限內容。
- worker token fencing 防止舊工作覆寫重試结果；pause／取消／expiry／未知接受在 ledger 保持可追溯狀態。錯誤記錄使用類型和 trace ID，不印 credentials 或原始證據。

## 尚未認定完成的控制

正式 MFA、IdP 邀請與 tenant onboarding、R2 signed tokens/生命周期、影片簽章、malware provider、正式事件分類／webhook、SIEM/on-call、異地加密備份仍有工程／啟用／驗證缺口。集中 distributed rate limits 已以 Redis 原子窗口補上；正式 Redis ACL／TLS／HA、edge client-IP 信任與容量仍待驗收。內部維運彙總只接受目前租戶的 PM／platform admin，拒絕 project delegation；不提供原始證據或自動重送。詳 [資安架構](SECURITY_ARCHITECTURE.md)。系統沒有聲稱已通過外部滲透測試或認證。

保存政策資料表原有項目仍是未核定草案。新增的 server 草稿、private archive、退場與 erasure executor 已完成本機實作和合成隔離測試，詳 `data-lifecycle.md`。正式 legal basis、各資料類別保存日數、legal hold、備份淘汰及 DSAR 身分核對未核定前，不啟用 destructive purge。本次僅刪除新建測試專用 tenant；既有資料保留。QA-20 的異地 key recovery／正式規模仍未通過。

## 備份與回復

`scripts/backup_restore.py` 與 `infra/verify_restore.py` 僅對明確 allowlisted DB／local object 來源工作。保留原始備份，在另一個 target DB 執行 restore；驗證逐表 row count/digest、object bytes/hash 和 schema revisions。第一份 65 tables/156 rows/1 object 的檢查點保留，新版結果以 `infra/evidence` 收據為準。這是本機還原證據；不代表正式規模 RPO/RTO 或異地 key recovery 已通過。

如遇 queue/付款未知，先保存 job、claim、ledger、provider reference 與備份；不要清表／清 queue／直接調餘額。依 billing-policy 與 project-operations 的補償路徑處理。
