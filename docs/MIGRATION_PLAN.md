# Partner Platform 增量計畫

基線：`96ec019`，2026-09-10；既有80表、資安七服務、資料、帳本與已發布報告保留。本輪規格為 `partner-platform-update-spec.md`。

1. 盤點並保留兩個產品的唯一業務寫入者；新增 Partner 歸屬、branding、domain、feature 與 session context，沿用 `tenant_id`，不重新編號既有客戶／專案。
2. 主官網改為商家 SaaS；新增 Partner 與商家登入路由。保留原資安客戶／學員與內部路由，舊公開服務頁改為 Partner 服務入口。
3. Partner 只看明示歸屬客戶的摘要；進入客戶工作台另需個人服務授權，沿用既有 session、membership、project grant 與 RLS。撤銷 Partner 或客戶連結時，既有委派 session 也失效。
4. Custom domain 先驗 ownership，再確認 TLS／預期 routing，未啟用網域不可用於登入。中央登入只接受精確已核定目的地，跨網域採一次性 code＋目標 host cookie binding，不共享 Domain cookie。
5. 前後台接 API，新增隔離／角色／domain／OAuth／旗標／計費投影測試。只用新增合成設定與測試身分驗證；部署先 Staging，外部啟用集中列 `MANUAL_ACTIONS_REQUIRED.md`。

## 點餐產品界線

既有 Stallorder 在另一個工作區，當前 HEAD `d506ff58e538bcca72045302ddca291ec85ab91b`，有未提交修改和多個 worktrees。以 CodeGraph 唯讀核實已有 Plan、PlanVersion、UsageEvent、Invoice、BillingCreditAdjustment、PAYG 與 feature flags。這些資料與收費交易繼續由原產品管理；本專案不建立第二套訂單、出單或應收帳本。

本輪新增可配置產品入口與官網價目投影，NT$1 為新文件指定的公開方案。網站價格不會直接啟用原產品收費；正式計費仍需原產品有效版本、稅務條款與發布旗標。`app.kuanguard.com` 對應既有商家產品的 domain／SSO 接入需要另核對來源正式設定，既有 `app.qidaigo.com` 入口保持可用。

## 相容與回復

目前無 KUANGUARD 公網部署，仍保留所有既有本機URL。新 `partner.kuanguard.com` 與 Partner custom domains 使用同一套程式；原 `app.kuanguard.com` 資安客戶路由以相容路徑保留，正式切換前先公告並驗證客戶 session 與書籤。

新增 migration 前後保存筆數與 immutable object checksums。回復程式保留新增表及歷史，不做 DROP／wipe，不重新寄出 unknown mail 或重扣點數。CUA browser automation 先前遭管理政策拒絕；本輪不繞過，HTTP／後端／結構驗證與瀏覽器視覺證據分開記錄。

## 已執行的 0011

權威入口為 `scripts/migrate.py` 中 `0011_20260910_partner_platform`，只新增 `partner_models.PARTNER_TABLES` 的 22 表、對應 tenant RLS 和 immutable triggers／grants，再安裝缺失 catalog。已存在 revision 時不重建；凍結的 `0001_initial.sql` 不變。

先從既有已驗證備份 restore 到 `kuanguard_restore_partner_20260910` 演練，完成後才套用本機 `kuanguard`。兩次皆 80 → 102 tables，原 811 筆逐列 hash 保留；合成 Partner seed 後當時共 873 筆。後續測試只新增合成資料／session，所以最新 backup row count 可大於 873。收據：`evidence/partner-migration-rehearse.json`、`evidence/partner-migration-apply.json`。

新增表按用途：10 個 bootstrap/platform tables；12 個 tenant-owned tables，包括 branding/assets、customer links/grants、tenant/plan features、commission rules/settlements/records、credit allocations、audit contexts、tenant IdP。具體 RLS 例外與保護方式見 [MULTI_TENANT_SECURITY](MULTI_TENANT_SECURITY.md)。未改既有 tenant/project IDs 或業務 ledger。
