# Partner 與平台 RBAC

| Partner role | Partner 功能 | 可授予的客戶服務角色 |
| --- | --- | --- |
| partner_admin | 客戶、個人授權、點數、branding、domain、audit | pm、customer_contact、customer_admin、campaign_manager、training_manager |
| partner_engineer | 客戶摘要／自己的服務 workspace | engineer |
| partner_reviewer | 客戶摘要／自己的服務 workspace | reviewer |
| partner_sales | 建立客戶、客戶摘要／自己的 workspace | pm、customer_contact |
| partner_finance | 錢包／分配點數、自己的 workspace | finance、billing_manager |

每個服務角色仍受原有 API 權限、工作階段、專案 grants、工程師／覆核分離和發行規則限制。Partner admin 不自動取得 engineer/reviewer/finance 客戶角色；必須綁定適當 Partner 身分和個別授權。能看歸屬摘要不代表能讀完整專案。

Platform admin 綁定 `platform_memberships` 的 active user，且透過 internal surface/Cloudflare Access；可管理組織、既有身分 membership、features、domain 狀態、公開方案與 leads。一般 customer_admin 和 portfolio_owner 身分不自動成為平台管理員；僅合成 owner-a fixture 明示加入平台管理。

沒有公開「自選角色」註冊流程。新增成員先完成外部 IdP 身分核驗，再由 platform admin 綁定既有 user ID。建立 Partner/customer 只建立組織，不會靜默寄邀請信或產生正式帳戶。
