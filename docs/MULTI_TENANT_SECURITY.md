# 多租戶安全邊界

每筆業務資料沿用 tenant_id。Partner 不把多家客戶資料混存同一 tenant；只透過明示 customer link 與個人 delegated access 取得授權。所有客戶操作使用原 tenant 交易上下文、伺服器角色與 project IDs，不信任前端選擇器。

PostgreSQL application role 為非 owner、NOBYPASSRLS。新增 12 個 tenant-owned tables 均 ENABLE/FORCE RLS，policy 為 `tenant_id = current_setting('app.tenant_id', true)`；transaction-local scope 防止 pool 串戶。新增 10 個登入前／platform bootstrap tables 需在 tenant 選定前查詢，因此不套 tenant RLS：organization_profiles、tenant_domains、session_contexts、portal_login_intents、portal_oidc_links、platform_memberships、product_registry、platform_leads、analytics_daily、feature_definitions。這些表靠精確 lookup 或 platform admin endpoint 授權，沒有公開 bulk secret／membership API。不能宣稱所有表都有 RLS。

新增 immutable 表為 credit_allocations、audit_contexts、partner_commission_records，使用 DB trigger 並撤銷 application UPDATE/DELETE。原 wallet、report snapshot、publication、audit 等限制保留。

跨 Partner mutating transaction 依 tenant ID 排序鎖定，之後重新驗證 session/授權，防止 TOCTOU。Personal grant 有期限與職務 ceiling，新增專案時只把该新 project ID 加入操作者自己的授權。平台管理權限不是從一般 tenant admin 推定。

Branding 不接受 HTML/CSS/SVG。文字作一般文字呈現；色碼只接受 hex；PNG/JPEG/WebP 限大小／像素後重新編碼，清除原有 metadata。只有該 tenant 目前 branding 引用的 asset 才能透過受限 public endpoint 下載，其他物件與報告仍是私有。主色由 Partner 設定後仍需人工檢查品牌配色對比。

CORS 無 wildcard，custom Origin 需 ACTIVE、verified、TLS active、Partner active 與 custom_domain flag；停用 Partner/feature 立即撤銷。Session 同時綁 Host，因此允許另一個精確 Origin 也不等於可跨站操作。

Audit 增加 actor、role、partner、tenant、resource、trace ID、IP hash、UA 與變更 before/after sidecar。沒有紀錄 session/token/DNS challenge 明文。個人資料匯出排除 auth intent；既有精確 erasure 清冊已納入 auth sidecar FK 順序，實際 erasure 只在測試用 tenant 驗證。

測試覆蓋隔離、角色提升、Host spoof、open redirect、OAuth 重放、branding XSS、FEFO 並行分配與不可改寫帳本。瀏覽器互動、edge WAF、正式 IdP 及侵入式外部掃描未列為已驗證。
