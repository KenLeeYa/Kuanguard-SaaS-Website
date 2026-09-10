# KUANGUARD DNS 與邊界接入操作手冊

查核日期：2026-09-10，已套用 v1.1 增量路由。本機工具與回復測試完成，既有 Cloudflare account／active Account Token 已唯讀驗證；KUANGUARD zone、正式 origin 與委派切換仍待啟用。網域固定 `kuanguard.com`；GoDaddy 註冊商保留。這份文件不是正式上線證明。

apex / www / app 改由 Vercel 專用 Projects 承載並強制 Cloudflare DNS-only，www redirect 由 Vercel 保留 path/query。admin 與 /portfolio 採資安專用容器 Tunnel＋Access＋應用授權；api 公開路徑拒絕 internal。既有 local Compose、資料與 backup 證據保留；Vercel / Supabase 共享管理層的 live inventory 見 `docs/shared-saas-inventory.md`。

## 現況與證據

`infra/evidence/public-verification-20260910.json` 記錄兩個 recursive resolvers（1.1.1.1、8.8.8.8）及實際權威 NS 的唯讀查詢。觀察到 `ns37.domaincontrol.com`、`ns38.domaincontrol.com`，apex A 為 `76.223.105.230` 與 `13.248.243.5`。這些是當時既有紀錄，不能當作新平台 origin 或擅自覆蓋。

apex 的 MX/TXT/CAA/AAAA 與 parent DS 查詢當時沒有 requested-type answer；回傳 SOA 並不表示收到 MX 或 DS。公開查詢無法枚舉完整 zone、所有子域或委派，因此完整原 DNS 匯出仍待提供。DNSSEC chain 未驗證。apex / www 公開憑證檢查成功，app / admin 檢查失敗；公開憑證不證明 origin TLS，也不證明本平台已部署。

Cloudflare account 已核對為 `b1c70202652cd3b77dfec70e5463785f`；以既有 token 查詢該 account 的 `kuanguard.com` zones 回覆空清單，仍需確認 scope 或專用 zone onboarding。KUANGUARD zone_id / assigned nameservers 維持 `null`；QIDAIGO 的 zone／NS 不能代用。證據見 `infra/evidence/cloudflare-discovery-20260910.json`，機器狀態見 `docs/cloudflare-status.json`。

已用交付的 CLI 實際執行 `inspect --config infra/cloudflare/desired.example.json --out infra/evidence/cloudflare-inspect-20260910`，回覆 `pending_action`；`discovery.json` 記錄 account readback success / token active / visible_zone_id null。此目錄沒有 snapshot 或 DNS 匯出，不能接續 apply。

## 設定事實來源與工具範圍

使用官方 REST API v4，adapter `1.1.0`；沒有 Terraform state 或平行第二套寫入來源。官方 endpoint 與查核來源記錄在 `infra/cloudflare/provider-contract.json`。

`scripts/cloudflare-onboard` 與 `scripts/cloudflare_onboard.py` 是相同 CLI。支援 inspect、plan、apply、verify、rollback。正式帳號的 endpoint smoke 尚待權限配置，單元測試使用明確 synthetic fake provider。

工具只管理明確列入的 application A/AAAA/CNAME。可用名稱限定 apex、www、app、admin、api、assets、status。apex/www/app 的 proxied=true 一律拒絕，其他 Vercel CNAME target 也拒絕 proxy；admin 必須是真實 Tunnel UUID 的 cfargotunnel.com CNAME 且 proxied=true。MX/TXT/CAA/SRV/NS 及 notify / sim 等郵件或演練名稱不由此工具修改。從宣告清單移除一筆不會自動刪除；必須保留同一個 key 並明寫 `state: absent`，而且紀錄已帶 `kuanguard-managed:<key>` 才能刪除。

`zone_id` 未填時，inspect 只執行固定 account／apex 的唯讀 discovery，輸出 `discovery.json` 與 `pending_action`，不生成可供 plan 的 snapshot。新 zone 建立與舊 DNS 初始完整匯入須先在已授權帳號完成，再以實際 IDs inspect / reconcile。HTTP transport 限制明確 methods／endpoints，寫入前綁定不可改變的 account＋zone；工具沒有 create-zone、整區 replace、zone delete、registrar NS/DS write 或郵件發送功能。

## 1. 建立可審閱的接入計畫

1. 既有 Account Token 已 active，後續確認 `kuanguard.com` zone scope；inspect 需要 Zone Read / DNS Read，apply 需要 DNS Write。缺 zone 時 discovery 另使用 Account Read。DNSSEC / TLS settings 的讀取可另需權限，403 會單項標示未驗證。Zone 建立、Access、Rules、R2、Stream 採各自必要權限；不要索取 Global API Key。
2. 把 `infra/cloudflare/desired.example.json` 複製至忽略提交的 `infra/cloudflare/private/desired.json`。保留已核對的 account_id，填入 readback 證實的 zone_id，並把供應商實際 origin 加入 `managed_records`。空清單、缺 target、保留測試網域與非 public IP 都會拒絕 plan。
3. 由目前權威 DNS 供應商取得完整 BIND / 正式匯出，包含原 TTL、A/AAAA/CNAME/MX/TXT/CAA/SRV、子域委派；另外記錄 registrar 的 NS/DS 與 TTL。建立一份候選 Cloudflare zone 對照表，逐筆確認郵件、CAA 與委派等原服務保留。
4. 依 `authority-proof.example.json` 填入真實匯出與對照表的絕對路徑、SHA-256、覆核者及時間；只有完整覆核後才將 `complete_zone_export`、`reconciled_into_cloudflare` 設為 true。這是操作人員的完整性聲明，工具能驗證檔案與 hash，不能用公開 DNS 自動證明未公開紀錄不存在。
5. 在 secret manager / process environment 配置 `CLOUDFLARE_API_TOKEN`；不放入 JSON、repo 或 terminal history。DNS 匯出、plan、receipt 可能含敏感 TXT 與內部 host，存放 private 目錄並限制存取、加密備份。

每個 desired entry 的欄位：`key`（穩定英數 key）、`name`、`type`、`content`（實際 origin）、`ttl`、`proxied`。proxied 必須明寫 true/false，proxied TTL 用 1。要接管既有紀錄，另外填 `adopt_id` 與 inspect 中該筆完整 record 的 canonical JSON SHA-256；未明確接管的既有同名紀錄會阻擋。

```powershell
uv run python scripts/cloudflare-onboard inspect --config infra/cloudflare/private/desired.json --out infra/cloudflare/private/inspect-01
uv run python scripts/cloudflare-onboard plan --config infra/cloudflare/private/desired.json --snapshot infra/cloudflare/private/inspect-01/snapshot.json --authority-proof infra/cloudflare/private/authority-proof.json --out infra/cloudflare/private/plan-01.json
```

inspect 先讀全部分頁，匯出 BIND，再讀一次全部紀錄；兩次一致才寫出 snapshot。plan 包含 target、原值/新值、保留紀錄數、export hashes、完整原權威匯出證據與 30 分鐘有效期限。用 editor 審閱具體差異、部署 commit / origin 與回復窗口，再確認輸出的 exact `plan_sha256`。

## 2. 套用與驗證

以下命令只在已完成具體 plan 覆核與切換授權後使用。`PLAN_HASH_FROM_REVIEW` 需替換為實際輸出，不能直接使用範例文字。

```powershell
uv run python scripts/cloudflare-onboard apply --plan infra/cloudflare/private/plan-01.json --approve-plan-sha256 PLAN_HASH_FROM_REVIEW --receipt infra/cloudflare/private/apply-01.json
uv run python scripts/cloudflare-onboard verify --config infra/cloudflare/private/desired.json --include-public --tls --out infra/cloudflare/private/verify-01.json
```

apply 重新計算 plan、檢查期限與備份，並對 account / zone / apex 作 fresh readback；整個 DNS inventory 一有 drift 就拒絕。每筆寫入之前先持久化 `prepared` journal，寫入回應確認後改為 `confirmed`，逐筆核對剩餘 inventory。更新使用 PATCH 保留非本工具控制的 metadata，沒有整區取代。

官方 DNS API 沒有此工具可使用的跨多筆 transaction / compare-and-swap 鎖。兩次讀取間仍存在競爭窗口；切換期間應凍結其他 DNS 管理員與 IaC 寫入。失聯或 timeout 不自動重送，receipt 會標 `needs_reconciliation`。先 inspect 確認 provider 實際結果，保留 journal，由操作人員產生新計畫；不要把 unknown 當 failed 後重複建立。

成功後重新 inspect / plan，應為 `actions: []`。verify 的 API match、zone active、public DNS、public TLS 各自輸出；它不聲稱已完成郵件、付款、origin TLS、Access 或應用流程。

無 Cloudflare 憑證時可獨立進行唯讀公開觀測：

```powershell
uv run python scripts/cloudflare-onboard verify --public-only --tls --out infra/cloudflare/private/public-observation-02.json
```

public verify 查詢兩解析器與每個已觀察到的權威 NS，保留 answer / authority / TTL / AD / AA。提供真實 Cloudflare assigned NS 才比較委派。DNSSEC 比對使用兩解析器 AD 與 provider DS；工具不是獨立 DNSSEC validator，正式切換仍須 parent DS / DNSKEY chain 的獨立驗證。

## 3. GoDaddy NS 與 DNSSEC 切換

正式變更前先確保候選 origin 已部署到確定 commit，備份、驗證與回復條件都完成。這個階段尚未執行。

1. 保留舊 DNS 供應商運作與完整 zone，不先刪除舊 zone。必要的 TTL 調整須提前按當時 TTL 等待傳播。
2. 先核對 `.com` parent DS、舊 DNSKEY 與現況。若舊 provider 支援官方 multi-signer active migration，可依相容方案安排；否則移除 registrar 舊 DS，保留舊 provider signing 到 parent DS TTL 真正到期，再確認 validating resolvers 沒有殘留舊 DS。
3. Cloudflare inspect 回傳 `assigned_nameservers` 後，登入 GoDaddy → 選擇 `kuanguard.com` → DNS → Nameservers → Change nameservers，輸入實際分配的完整名稱並完成必要 2FA。註冊商不轉移。若 session/API 資格不足，由帳號持有人完成此一步；沒有憑證就沒有可安全替代的自動寫入。
4. 記錄更新時間，查每個新權威 NS、至少兩個 recursive resolvers、parent delegation 與 zone active；依實際 NS/DS TTL 觀察，不能假定即時切換。
5. 穩定後在 Cloudflare 啟用 DNSSEC，取得實際 key tag / algorithm / digest type / digest，再在 GoDaddy 配置新 DS，等待傳播並驗證 DS→DNSKEY→RRSIG chain。不要永久關閉 DNSSEC，也不要讓舊 DS 指向新供應商不存在的 key。
6. 完成 www 永久 redirect 的 path/query 保留、登入、客戶與員工權限、signed webhook、private download no-store，以及已獲授權測試信箱往返驗證。未指定測試信箱時維持未驗證，不自行寄給第三人。

官方依據：[DNSSEC 遷移與回復](https://developers.cloudflare.com/dns/dnssec/)、[GoDaddy nameserver 操作](https://www.godaddy.com/help/change-my-domain-nameservers-664)、[Cloudflare zone 匯出](https://developers.cloudflare.com/dns/manage-dns-records/how-to/import-and-export/)。

## 4. 最小回復

DNS record 回復以實際 apply receipt 為範圍。輸入逐項覆核後的 receipt hash：

```powershell
uv run python scripts/cloudflare-onboard rollback --receipt infra/cloudflare/private/apply-01.json --approve-receipt-sha256 RECEIPT_HASH_FROM_REVIEW --out infra/cloudflare/private/rollback-01.json
```

rollback 只刪除本次建立且仍未變動的 owned record、把本次 PATCH 還原成原值，或重建本次刪除的 owned record。原 record ID 在重建後可能不同，內容與 metadata 會復原。若紀錄已被其他人修改、name 被重新使用、journal 有 unknown outcome，就停止；不刪整個 zone，也不碰未管理郵件紀錄。

應用版本回復使用先前已驗證的 immutable image / commit；DB schema 相容性需另外核對。若需 NS 回復，先確保舊 DNS zone 完整且仍運作，配合 registrar DS 回到與舊 provider 相容的組合。移除新 DS 後保留新端 signing 直到 parent TTL 到期，再依核定步驟切回；不要把 record rollback 當作 NS/DS rollback。每一步重新驗證，TTL 期間的混合解析是必須列入的回復時間。

## 5. 邊界資源尚待啟用

`infra/cloudflare/edge-policy.intent.json` 是可審閱 intent，尚未安裝 Rules/Access/R2/Stream。Vercel DNS-only hosts 使用 Vercel 的 TLS/CDN/firewall，不宣稱受到 Cloudflare WAF/Access 保護。只有適用的 proxied HTTP origin 在驗證 chain/hostname 後設定 Full (strict)；Tunnel 採其適用連線設計。WAF、rate limits、Turnstile、origin 防直連與通知 destination 依實際方案與測試授權配置。

app 的敏感回應在 Vercel no-store，admin/API 與適用 Cloudflare proxy 路徑維持 origin `private, no-store` 且 edge bypass；不設定全站 Cache Everything。Access 僅限 admin，初始名單使用目前 owner，origin 必須驗證 JWT signature / issuer / audience / expiry 並保留應用 RBAC。`tunnel.example.yml` 另外要求 cloudflared 驗證 Access token；不得公開 admin container port。callback 使用獨立 policy，不能把整個 API 白名單；webhook 仍驗簽。HSTS 暫不加 includeSubDomains / preload。

R2 私有 quarantine / evidence / reports 與 public assets 分 bucket；地域條款須先核定。S3 presigned URLs 用實際 S3 endpoint，不能換成自訂 host。Stream 需 enrollment 後發短效 token 並設 requireSignedURLs；付費完整影片不當 preview，簽章不等於 DRM。依據：[cache bypass](https://developers.cloudflare.com/cache/how-to/cache-rules/settings/)、[R2 presigned URL 限制](https://developers.cloudflare.com/r2/api/s3/presigned-urls/)。
