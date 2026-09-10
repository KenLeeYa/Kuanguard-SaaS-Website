# Partner 操作與資料歸屬

本輪可操作：總覽、歸屬客戶、建立獨立客戶 tenant、個人角色／專案／期限授權、服務工作台、點數分配、branding、網域註冊／驗證／停用、稽核與平台 feature flags。

本機啟動後只需一次明示執行 `uv run python scripts/seed_partners.py` 安裝合成 Partner fixture；重跑保留既有資料。此命令只容許 development/test，不能建立正式三傑帳戶。首次初始化一般專案仍先使用既有 `start-local.ps1`。

1. `/partner/login` 選 Partner slug；本機三傑使用 `megaprotek`，第二夥伴為 `example-partner`。選擇已存在的合成角色後登入。
2. Dashboard 僅列該 Partner 的客戶摘要。Partner admin 或 sales 可建立客戶，但建立資料不會邀請外部人員或寄信。
3. 管理員在客戶授權中選既有 Partner 身分、角色、該客戶的 project IDs 與最長 90 天到期日。授權不得高於對方 Partner 職務。
4. 「進入服務工作台」撤銷原 session，建立客戶 tenant 的委派 session。原有匯入、覆核、報告、排程、複測、變更、派工與點數路由沿用既有程式。
5. 返回 Partner 時再輪替 session。Partner、membership、客戶關係、個人 grant 或 feature 撤銷會在下一個請求生效。

`partner_customers.tenant_id` 為目前 owning partner，另記 `customer_source`、`originating_partner_id`、`account_manager_id`、`contract_owner`、`service_provider`。每位客戶當前僅一個 owning partner；不提供未經審查的跨 Partner 批量移轉 API。客戶自己的 membership 可由既有客戶入口登入，獨立於 Partner 服務授權。

保留 VA、WVA、PT、SHC、SOURCE、社交工程演練、LMS 七服務。委派不跳過工程師／覆核分工、發行規則或報告權利驗證。工程師只看授權專案；財務與業務權限見 [RBAC](RBAC.md)。

Commission 頁明示停用，目前只回傳規則與結算資料基礎。Enterprise SSO、referral 與 onboarding automation 列 P2；不能靠開啟 planned flag 宣稱可用。
