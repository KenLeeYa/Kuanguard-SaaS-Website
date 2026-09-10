# Partner increment 驗證報告 — 2026-09-10

| 驗證 | 結果／證據 |
| --- | --- |
| Python 全套 | 250 passed、45 subtests passed；2 個既有第三方 deprecation warnings；[JUnit](evidence/partner-tests-20260910.xml) |
| 新增 backend cases | Partner isolation／delegation／credits／branding/domain；OIDC／HMAC；PostgreSQL FORCE RLS 與並行分配 |
| Ruff | backend/scripts/tests passed |
| OpenAPI | 246 paths，export/check 相符 |
| 前端 | 13 tests passed；TypeScript passed；Next production build passed |
| 真實 HTTP | 91 項：官網 17 routes、canonical、headers、static assets、BFF、角色／委派、中央登入與 replay；重啟最新 API 後 [receipt](evidence/partner-http-final-20260910.json) |
| Migration rehearsal | 新 restore DB 先演練，再套本機；[rehearse](evidence/partner-migration-rehearse.json)／[apply](evidence/partner-migration-apply.json) |
| 資料保留 | 80 → 102 tables；原 811 筆逐列 hash 不變；seed 後當時為 873 筆 |

實際 HTTP 曾發現 Node fetch 不會按自訂 Host 轉送，現以 mandatory BFF HMAC 與 shared secret 修復。HTTP 驗證證明 PENDING 三傑及未知 Host 回 404，偽造 X-Forwarded-Host 不會啟用網域。前端 contract tests 同時驗證缺 key fail-closed、固定 API origin 與精確 path/query 簽章。

PostgreSQL 使用 NOBYPASSRLS application role，驗證 tenant scope reset、同一 Partner 12 次並行分配只接受可用的 5 筆、來源 5 → 0，目的客戶共 5，receipt/audit 不可 UPDATE/DELETE。這些測試只新增合成 tenant，完成後歸檔；不清空既有資料。

OIDC 測試使用合成 RSA keys 與 provider transport，覆蓋 state、PKCE、nonce、issuer、audience、到期及 code/binding replay。真實 HTTP 在 Node→Python→PostgreSQL 上使用 development identity completion，沒有呼叫正式 IdP。Partner 角色與客戶權利測試不等於正式外部合作验收。

四個 Docker image 均以 non-root UID 10001、network-none、無來源 DB／object mount 進行 smoke，含 public surface 的 admin 拒絕與未配置 BFF fail-closed。最終 raw source binding 見 [images](../infra/evidence/partner-images-final-20260910.json)。收尾只恢復四個舊檔未修改行的原 newline bytes，前後語意內容一致，避免無關整檔 diff；映像依最終 bytes 重建。

新增完整 backup/restore：102 tables、1,087 rows、36 objects／1,165,681 bytes；table native-JSON checksum 與來源／備份／還原物件 SHA256 全部一致。Manifest `681a9f6316c406ee9024c2afb0b4f1e718eaf1d2f3f12cf69f769dbfa964825c`，保留並重新驗證先前三份備份。見 [backup receipt](../infra/evidence/backup-restore-partner-final-20260910.json) 與 [table comparison](../infra/evidence/backup-restore-partner-final-table-comparison-20260910.json)。備份後的 HTTP 登入驗收另新增／撤銷合成 session，不改業務資料；backup 筆數代表其停寫時間點。

舊 v1.1 receipt 保留為基線，不作為這次變更完成的證據。GitHub CI 狀態以該提交的 Actions 為準。

限制：管理政策拒絕 CUA browser automation，未繞過；因此沒有 desktop/tablet/mobile 視覺、完整鍵盤／focus、a11y browser、錄影及真實 IdP/device/TLS E2E 的通過宣稱。Responsive CSS、labels、focus/reduced-motion 與既有文字配色 contract 已檢查，但仍須在允許的互動瀏覽器中驗收。外部 Staging/Production、金流、外送、SSO、寄信、報告公司核准模板／字型及 DR RPO/RTO 尚未核定。
