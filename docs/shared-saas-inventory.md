# 共用 SaaS 帳戶與專用資源清冊

2026-09-10 v1.1 增量盤點。使用者已決定同一 owner 共用 Cloudflare Account、Vercel Team、Supabase Organization；不邀請第二位管理員、不搬移既有產品。以 provider 唯讀 API 核對實際 IDs，再規劃 KUANGUARD 專用資源。

## 已取得的 live readback

| Provider | 共用管理範圍 | 已驗證現況 | KUANGUARD 差距 |
| --- | --- | --- | --- |
| Vercel | Team `team_MMfsiG94K9Zy3e6w7Ccc9xY4`，slug `ada76145-8663s-projects` | Team plan `pro`；現有 `stallorder-platform` 與 `beauty-saas-platform` | 清單未見 KUANGUARD Project；不接管既有兩個 Project |
| Supabase | Organization `urxujyhcggjgwsjtleys`，名稱 `KuanGuard` | live get_organization 回覆 `pro`；已有三個非本次資安 Project | Org 名稱不等於已存在資安 DB；Production／nonproduction 專用 Projects 尚待建立 |
| Cloudflare | Account `b1c70202652cd3b77dfec70e5463785f` | 既有 Account Token 狀態 active；account 與 qidaigo.com 所屬 account 相符 | 指定 account 與 kuanguard.com 的唯讀 zone 查詢為空；確認 token scope／專用 zone onboarding；Tunnel / Access / buckets 尚未驗證 |
| GoDaddy | 既有 `kuanguard.com` 註冊 | 使用者確認購買；公開 NS 為 ns37/ns38.domaincontrol.com | registrar console / DS / 完整 zone 匯出仍待存取 |

現有非 KUANGUARD 資源僅作防誤接識別：

| 產品資源 | ID | 狀態／地區 |
| --- | --- | --- |
| Vercel stallorder-platform | `prj_uoG4FNJIgnF1LdKRiXnfRaieXnUP` | 已有部署，唯讀查核 |
| Vercel beauty-saas-platform | `prj_S8ryMyEGjyenihjsJTU8QZqAUI2I` | 本次不操作 |
| Supabase stallorder-production | `eyuctbnlvnbnivwasvqr` | ACTIVE_HEALTHY / ap-northeast-1 |
| Supabase stallorder-dr | `daeqwtpaxcebmtwxqdkj` | ACTIVE_HEALTHY / ap-northeast-1 |
| Supabase beauty-saas-production | `dfuhylsmhrysbmhpeylx` | ACTIVE_HEALTHY / ap-northeast-1 |
| Cloudflare qidaigo.com zone | `8f8070a80ad4182e4af0c11a1b496968` | active；只用於核對同一 account，不能成為本工具寫入目標 |

KUANGUARD 不能使用以上 Project IDs、DB credentials 或 buckets。東京是既有其他產品的 live metadata，資安地域仍待合約核定。清冊只記非秘密 identifiers，沒有讀出 service_role、資料庫 password 或完整客戶資料。

原始安全摘要：`infra/evidence/shared-saas-inventory-20260910.json`。部署計畫：`infra/deployment-plan-v1.1.json`，所有新資源 IDs 留空直到實際建立並回讀。先確認現有同名資源，沒有才按核定成本建立；重跑不得多建相同 product/environment 資源。

Cloudflare readback 見 `infra/evidence/cloudflare-discovery-20260910.json`。最初 user-token verify 回覆 401；改用官方 account-token verify endpoint 後為 active，並非 token 不存在。空的 KUANGUARD zone 清單只代表目前 token 可見範圍，不能證明所有帳號均無該 zone。未輸出 token 值、未寫入 DNS，也未把 QIDAIGO nameservers 當成 KUANGUARD assigned NS。

## 目標配置與環境界線

| 執行面 | Production | 非正式環境 |
| --- | --- | --- |
| Vercel | 資安專用 public / customer-learner Projects；apex、www、app DNS-only | 資安專用 Preview / test 部署與獨立非正式 credentials；拒用 production secrets |
| Supabase | 資安專用 Project；FastAPI 為唯一業務寫入者 | 另一個資安 Project；不複用 production 或 QIDAIGO DB |
| 容器 | 資安 API、admin、report workers、Gophish、queue；各自資源限制 | 保留已完成的 local Compose 與 restored DB 作測試；不因更新而重建 |
| Cloudflare | kuanguard zone、admin Tunnel＋Access、R2 scope credentials、適用 API 規則 | 獨立 environment resources / secrets；所有變更固定 kuanguard 範圍 |
| 帳務／郵件 | KUANGUARD ledger、商品、order mapping、通知與演練 sender profiles | sandbox keys / 受限測試信箱；與訂餐交易通知分開 |

Supabase project-scoped Dashboard roles 目前限 Team / Enterprise。單一 owner 的架構可沿用既有 Pro Org；工程師使用應用內職務權限，沒有必要為本次任務升級方案或新增 SaaS 控制台成員。日後真正需要只看單一產品的雲端協作者再評估。[官方角色說明](https://supabase.com/docs/guides/platform/access-control)

同一 Account / Team / Org 的付款、停權、帳號復原與部分用量仍屬共同故障範圍；owner MFA / recovery 與產品 scope credentials 的獨立輪替需要並行維護。

## QIDAIGO source API 盤點

檢查 `C:/Users/KY/Documents/Codex projects/Stallorder-Platform` 時已先讀 AGENTS、HEAD/status 並確認 `.codegraph` 存在，再用 CodeGraph 定位。目前為 detached HEAD `d506ff58e538bcca72045302ddca291ec85ab91b`，工作樹原本已有變更，全部保留。

| 現有來源 | 可沿用部分 | 不可直接作 portfolio source 的原因 |
| --- | --- | --- |
| GET `/api/health`、`/api/health/primary` | 已有小型 status / timestamp DTO、no-store | 只證明 health，不含財務／產品授權 summary；本次未對正式健康端點發起測試 |
| `/api/merchant/dashboard/overview` | 商戶範圍 dashboard 路由存在 | merchant scope 不等於公司 portfolio 範圍，不重用商戶 session 或管理 key |
| `src/lib/admin-billing-data.ts:getAdminBillingOverview` | source-side monthlyInvoiced、monthlyCollected aggregation | 目前期間以 UTC 月初計算；回傳 pendingRequests / pendingPayments 有關聯明細；必須轉成受限 aggregate DTO，不能整包跨產品複製 |
| 現有 admin billing PATCH/POST | 維持來源核定/收款流程 | 全屬來源寫入，portfolio 首波不呼叫 |

在限定的 `src/app/api` inventory 未找到已具明確 portfolio read-only scope 的整產品 summary endpoint。這是 bounded code inventory 的結果，不宣稱已掃遍所有部署或未知 worktrees。最小來源端契約／patch proposal 放在 `docs/qidaigo-summary-contract.md`；需来源 owner 審閱、實作、授權與發布後才連線。沒有修改來源 schema、登入、出單或費率。

`qidaigo-readonly-baseline-20260910.json` 與 `qidaigo-readonly-final-20260910.json` 的 HEAD、status hash、tracked diff hash 完全一致。Vercel 首尾讀到同一 production deployment `dpl_6X7u13QaCXwXC9LUFvJytWjgvQRQ`（READY）；`infra/evidence/qidaigo-deployment-readonly-final-20260910.json` 記錄比對。本次無來源寫入、DNS mutation 或部署工具呼叫；沒有宣稱測過正式訂單出單。
