# Central authentication 與 Host-bound sessions

登入入口先分流 Merchant／Partner／平台管理／既有資安客戶及學員。Merchant 深連結至原產品；此專案不接受原產品 session token，也不在 URL 傳遞該 token。Platform admin 需要明示 platform membership 加 Access 保護。

1. 目標 portal 同源 POST `/auth/portal/start`。驗證 exact Origin/Host、Partner、可用 domain、tenant 與 allowlisted return path；目標不能由任意 URL 指定。
2. 建立 5 分鐘 intent，目標 host 設 HttpOnly SameSite=Lax browser-binding cookie。資料庫僅保存 intent 與 binding hash。
3. 在 `auth.kuanguard.com` 完成 OIDC authorization code + PKCE S256，驗證 state、nonce、RS256、issuer、audience、exp、iat、sub。`OIDC_REDIRECT_URI` 必須精確對應中央 callback；多 tenant 身分未選定企業時回 409，不自動選第一家。
4. 中央成功後發 60 秒一次性 code，返回已記錄目的地 `/api/auth/portal/callback`。此 code 不是 session token，且只有發起登入的 browser-binding cookie 可兌換。
5. 原子 consume、再次檢查成員／Partner／domain／到期，撤銷先前 session，設定新的 Host-bound、HttpOnly cookie。HTTPS 使用 Secure，不設定跨 eTLD 的 Domain cookie。303 回到固定路徑；callback 禁快取、no-referrer，避免 code 洩漏。

預設同源 BFF 固定連到 KUANGUARD API。`PORTAL_PROXY_SECRET` 只存在 server 環境；HMAC-SHA256 簽署 method、原始 path+query、實際 Host 與 timestamp，API 允許 60 秒時差。缺 key 時 BFF 回 503；錯簽／過期回 403。任意 X-Forwarded-Host 不影響租戶。不要將 key 放進 NEXT_PUBLIC_*，不要把使用者供給的 signed headers 直接轉送。

Session 每次請求重新查詢 active membership、tenant、Partner、客戶關係、個人 grant、feature 與專案 scope。所有 mutation 檢查 Origin/Host 與 CSRF；idempotency 和 expected_version 控制重試／並行。Partner 進入／返回客戶工作台均輪替 session。

本輪 OIDC 使用本機合成 RSA/IdP 回應測試，未呼叫真實 provider。Google、LINE、Apple、Microsoft Entra 的直接登入與企業 SAML 尚未實接；目前提供一個 generic OIDC broker 接口，tenant IdP schema 為 P2。development completion 只限 test/development，公網 gateway 額外拒絕。

威脅模型依 [OAuth 2.0 Security Best Current Practice, RFC 9700](https://www.rfc-editor.org/rfc/rfc9700) 的精確 redirect、PKCE、state/nonce 與避免 token 洩漏原則實作；本機測試不取代正式 IdP callback／browser／TLS 驗收。
