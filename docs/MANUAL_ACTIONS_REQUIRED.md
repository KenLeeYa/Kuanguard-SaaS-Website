# 需要 Owner／網域管理者／合作方的項目

資安 Phase 最新稽核見 [SECURITY_PHASE_STATUS](SECURITY_PHASE_STATUS.md)。Gophish／SMTP、Stream、R2、正式支付／發票與企業 onboarding 仍含程式工程，不能只提供 credentials 就當成完成。已補上的 Redis 限流與內部維運彙總不改變正式七服務共同 gate。

本輪能在現有本機安全完成的 P0/P1 程式、資料遷移與驗證已接續處理。以下是外部啟用所缺的帳號、權限、商业決策與第三方驗收，不影響本機程式操作；不得以假資料或關閉 release gate 取代。

| 項目 | 需要提供／決定 | 準備完成後的動作 |
| --- | --- | --- |
| KUANGUARD 獨立 Staging/Production | project/account IDs、region、預算與維運權限 | 核對資源歸屬；建立具體 migration/deploy plan |
| kuanguard.com DNS | 權威完整匯出、GoDaddy/Cloudflare zone 權限、nameserver 變更窗口 | 重取 discovery，比對 MX/TXT/CAA/其他 records，再審核 Apply |
| Partner hosting | Cloudflare for SaaS 方案、fallback origin、核定 CNAME target/DCV | 設 `CUSTOM_DOMAIN_TARGET`，先 Staging TLS 與隔離驗收 |
| 三傑科技 | 正式 Partner 合約／公司名稱、客服、logo 權利、實際成員 | 綁定正式 Partner，重發 TXT challenge；三傑 DNS 管理者設定 portal hostname |
| 中央身份 | OIDC issuer/client、精確 callback、Google/LINE/Apple/Entra console 權限與核定 provider | 以 secret manager 配置；逐一實測登入／撤銷；SAML 屬 P2 |
| 商家 app.kuanguard.com | 原商家產品的 domain/project/readback、SSO 接入決策 | 在來源正式工作流發布；保留既有 app.qidaigo.com 入口 |
| 每單 NT$1 方案 | 成功訂單定義、有效版本、稅務／退款／補貼條款 | 由來源 billing domain 綁定版本，先測 UsageEvent 和 invoice 再啟用 |
| 金流／發票／外送 | 商戶及 foodpanda/Uber Eats 等正式合作 credentials、合約與官方核准 | sandbox 驗收後獨立開通；目前 planned |
| 正式資安交付 | IdP、R2/Stream、Gophish/SMTP、核准報告字型／模板／教材與人員權利 | 接續原七服務 release checklist，保留 unknown 交易對帳限制 |
| 安全與法務 | Privacy/商家條款/Partner條款的營運主體、保存與 DR RPO/RTO、Access MFA | 核定文案、backup encryption、restore 演練、正式安全驗收 |
| 瀏覽器验收 | 允許的人工操作環境或管理政策變更 | 實測 390/768/1440、鍵盤與 focus、custom host TLS/login；本輪未繞過拒絕 |

P2 仍未實作完整功能：commission calculation/payout、tenant SAML/federated SSO、advanced CRM/analytics、referral、Partner onboarding automation。這些是後续工程項目，不是假稱只差 credentials 即可啟用。

Secrets 只由環境變數或 secret manager 傳入；不要貼到 issue、README、GitHub commit 或本機共享記錄。正式啟用前需重新核對遠端狀態，歷史 discovery 不代表目前仍相同。
