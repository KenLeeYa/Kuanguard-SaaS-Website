# 基礎設施與復原就緒度

日期：2026-09-10，已套用 v1.1 並接續原工作。本機 API／worker／web images 已建置並通過隔離 smoke，來源雜湊相符；0001–0010 與最新合成資料已獨立還原驗證。原 DB/data/Compose 及兩份舊備份保留。正式目標為 Vercel public/customer/learner＋獨立 Supabase Projects＋資安容器 API/admin/workers/Gophish；正式主機與外部服務尚未啟用。

## 已交付與驗證

| 項目 | 實作 | 證據與界限 |
| --- | --- | --- |
| DNS inspect / plan / apply / verify / rollback | `scripts/cloudflare_onboard.py`；官方 API v4；固定 apex / account / zone；完整備份、plan hash、30 分鐘期限、逐筆 journal、drift check | `tests/test_infra.py`；provider 使用 synthetic fake，沒有真實 DNS write |
| DNS 公開觀測 | locked dnspython；兩個 recursive resolvers＋每個實際權威 NS；A/AAAA/NS/SOA/MX/TXT/CAA/DS | `infra/evidence/public-verification-20260910.json`；不等於完整 zone export 或 DNSSEC chain |
| 容器 API / worker | pinned Python 3.12.14 image digest、uv 0.12.12、uv.lock、UID 10001、fonts-noto-cjk | 最後 build／隔離 smoke 通過，各60個 backend／scripts／lock／config 檔雜湊符合來源；`infra/evidence/final-increment-images-20260910.json` |
| 容器 web | pinned Node 24.21.0 LTS digest、package-lock、standalone、UID 10001；build/runtime API origin 與 internal surface 明確設定 | build／HTTP smoke、57個來源 manifest、private/no-store、static asset 與 www 308 通過；`infra/evidence/final-increment-images-20260910.json` |
| DB＋objects backup | SQLite online backup 或 PostgreSQL pg_dump custom；objects 對照及 hash；完整 manifest、public metadata / key refs | `scripts/backup_restore.py`；需暫停 mutable object / DB writes；工具不自行加密 |
| 安全 isolated restore | checksum 驗證在寫入前完成；新目錄與 allowed-root；拒絕 symlink/junction/path traversal、existing destination、production DB 名稱 | `tests/test_infra.py`；無刪除或覆寫現有資料 |
| 真實 PostgreSQL restore | local Compose db；新 database `kuanguard_restore_20260910_complete`；pg_restore single transaction | 80 張 public tables / 811 rows，逐表 count 與 ordered native JSON SHA-256 相同；36 objects hash 相同；原65表與67表備份保留 |
| 監控 | API/worker、mail/payment reconciliation、backup、TLS、DNS drift、成本監控定義 | `infra/monitoring/checks.json`；scheduler、告警接收者與實際通知尚未配置 |
| v1.1 DNS 路由 | Vercel apex/www/app DNS-only、admin 實際 Tunnel CNAME；public API allowlist gateway | 22 個 infrastructure tests 通過；新增精確 app/drafts 路徑；Tunnel/Access/gateways 是待啟用配置，未部署 |
| 共用 SaaS 清冊 | live Vercel Team / Supabase Org 均為 Pro；新專用 Project IDs 留 null | `docs/shared-saas-inventory.md`、`docs/shared-saas-costs.md`；本次外部新增資源為 0 |

Vercel DNS-only 流量使用 Vercel 防護；Cloudflare WAF/Access 不適用該路徑。admin `/portfolio` 要求 owner／explicit grant；public API 不代理 `/internal`。新 Supabase Project 的 compute 已取得每個約 US$10/月 quote，預算與資安地域未核定，因此沒有建立資源或遷移現有資料。

API、DB、queue、web、worker 的組合在 root `compose.yml`。PostgreSQL bind `127.0.0.1:55438`，容器内 `db:5432`；Redis 本機 bind `127.0.0.1:6388`。Compose 使用 private `object_data` volume；宿主開發程序使用 `.local/storage`。備份時必須選當時真正 serving 的 object source，不能拿空宿主目錄代表容器 volume 已備份。

worker 在 Compose 限制 1 CPU、1 GiB memory、128 pids；專用 queue 與既有服務／ports／volumes 保留。這是初始本機容器上限，正式容量需依代表性解析／報告負載量測調整。`docker compose build api worker` 只建置 image，不會套用執行期限制到現有 native 程序，也不會重啟 DB／queue。

API／worker 首次建置發現 Dockerfile 的 `COPY samples` 與根 `.dockerignore` 排除項衝突；確認 samples 僅由測試引用後移除該 COPY，未放寬 build context 或複製 secrets。兩個 image 在無網路、無 DB／object mounts 的暫時容器中，通過 API／worker import、原生依賴載入、UID/GID 10001 寫入／讀回及 checksum；實際 cgroup 分別讀到 1 CPU、1 GiB、128 pids。四個 CJK fallback font files 已存在，指定報告字型與 embedding QA 仍未證實。驗證程序為 `infra/image_smoke.py`；最終結果在 `infra/evidence/api-worker-image-smoke-runtime-20260910.json`。

建置前後 DB `c6a391867a0c`／queue `934d804c3fdc` 的 IDs、health、ports 完全一致。本次未執行 Compose up/down 或停止 native API/UI。先前建置曾正確偵測並行來源修改；該次 evidence 保留，最終採 `api-worker-build-runtime-20260910.json`。備份後 root 對啟動器作 UTC ticks 修正，因此只刷新 cached COPY 層，含 `.ps1` 在內的全部複製來源已重新對照相符。Root 於備份驗證完畢後啟動 native worker；上述 Docker 上限不宣稱限制 native 程序。

web 原本缺 Dockerfile，新增 `infra/Dockerfile.web` 與限定 build context 的 `apps/web/.dockerignore`。Compose 在建置與 runtime 均使用 `API_INTERNAL_URL=http://api:8180`、`DEPLOYMENT_SURFACE=internal`，admin gateway 對接現有 `web:3180`；同源 `/api`／`/internal` 仍直接交由 gateway 轉入 API 並保留 Host/JWT。Web image smoke 使用無網路、無 mounts、無公開 ports 的暫時容器，`/login`、`/portfolio`、`/overview` 回 200＋private/no-store；static asset 回 200，www 回 308 並保留 path/query。HTTP Host 測試使用原生 HTTP client，避免 fetch 對自訂 Host 的處理造成測試失真。容器均已移除；未驗證容器串接 live API／Access／正式 DNS。

Node LTS 版本與 image digest 經 AnySearch 官方版本頁及 registry readback 核對；未更動 web source／Next config／鎖檔。[Node.js 24.21.0 官方發布](https://nodejs.org/en/blog/release/v24.21.0)

## 保留的 U0–U4 還原檢查點

來源 local PostgreSQL `kuanguard` 經 owner `kuanguard_owner` 讀取。主流程完成最終測試與 UAT 後確認 writers paused；服務保持運行，沒有啟動 native worker。2026-09-10 08:01:20–08:01:32 UTC，還原至同一開發 cluster 全新 `kuanguard_restore_20260910_v11`，來源 DB／objects 未被本次演練修改；之後已通知可恢復 writers。

最新 archive／objects 在 `.local/backups/20260910-v1_1-final`，還原 object 在 `.local/restores/20260910-v1_1-final`，皆為不提交 Git 的 private data。manifest SHA-256：`4eb4394ad4ec8ecc2d564ec719dcb9d88e581542d622b7c25cf22b7135c4da03`。0001_initial 至 0006_service_ledger_immutable 全部保留；67 張表／642 rows 逐表筆數與原生 JSON SHA-256 相同，36 objects／1,165,681 bytes 的 source／archive／restored hashes 相同。非秘密結果見 `infra/evidence/backup-restore-v1_1-20260910.json` 及 `backup-restore-v1_1-table-comparison-20260910.json`。

首次 `.local/backups/20260910-local-drill`／`kuanguard_restore_20260910` 未刪除或覆寫，且原 manifest `b0713bed581a48ca07625b45adfd3a13232e0e90d27cfa12b80b6c4e1cded21f` 重新驗證通過。兩次都只證明本機 native schema/data restore 與檔案一致性；未執行 application job redrive、SMTP、付款、tenant export/delete 或 production-scale RPO/RTO 演練。

## U5 最新建置與還原

接回原工作後完成0007～0010，重新建置並逐檔核對三個映像，API/worker各60個來源與web57個來源無差異。Canonical receipt為 `infra/evidence/final-increment-images-20260910.json`；上方較早的 build／67表還原敘述是歷史檢查點。

2026-09-10 09:38 UTC，取得各tenant交易鎖並確認running jobs=0後，依本專案PID、啟動時間、執行檔與父子關係核對，只暫停 native API/worker；DB/queue/web保留。新增 `.local/backups/20260910-increment-complete` 並還原至全新 `kuanguard_restore_20260910_complete` 與 `.local/restores/20260910-increment-complete`。

80 tables／811 rows的逐表筆數和原生JSON SHA-256相同；36 objects／1,165,681 bytes在來源／備份／還原間相同。保留0001～0010 revisions。Manifest：`94ab88f754ab524a9b11151169d275db2ed5b3a0a476b1d6515e74233ccf1abd`；兩份舊manifest再次驗證通過。正式收據在 `infra/evidence/backup-restore-complete-20260910.json` 及 `backup-restore-complete-table-comparison-20260910.json`。

比對結束後用原啟動器的 `-SkipMigrations` 重新啟動 API/worker，不重跑seed／migration；本機health與新私有頁HTTP回200。沒有對備份中的job執行redrive，沒有對既有tenant做退場／刪除或對外寄送。這仍是本機一致性證據，不是正式異地加密復原或SLA。

## 可重跑命令

本機 API/worker 真正停止寫入、或維運已達成等效一致性窗口後，選一個全新備份名稱。`--writers-paused` 是操作者聲明，不會偷偷替你停止服務。

```powershell
uv run python scripts/backup_restore.py backup --postgres --compose-file compose.yml --database kuanguard --user kuanguard_owner --objects .local/storage --out .local/backups/NEXT_DRILL --writers-paused --metadata infra/backup-metadata.example.json
uv run python scripts/backup_restore.py verify --backup .local/backups/NEXT_DRILL --manifest-sha256 ACTUAL_MANIFEST_HASH
uv run python scripts/backup_restore.py restore --backup .local/backups/NEXT_DRILL --out .local/restores/NEXT_DRILL --allowed-root .local/restores --manifest-sha256 ACTUAL_MANIFEST_HASH --compose-file compose.yml --database kuanguard --user kuanguard_owner --target-database kuanguard_restore_next_drill
uv run python infra/verify_restore.py --compose-file compose.yml --source kuanguard --restored kuanguard_restore_next_drill --out infra/evidence/NEXT_DRILL-table-comparison.json
uv run python -m unittest discover -s tests -p test_infra.py -v
```

若使用已安裝的 PostgreSQL client，省略 `--compose-file`，從 secret manager 配置 PGHOST / PGPORT / PGPASSWORD；不要把 password 寫進 CLI。若只有 SQLite fixture，使用 `--sqlite .local/kuanguard.db` 取代 `--postgres`，restore 不傳 PostgreSQL arguments。

`infra/verify_restore.py` 對小型本機演練資料以單次 SQL snapshot 取得各 public table，按固定順序產生 canonical JSON SHA-256，與獨立還原 DB 逐表比較；保留寫入暫停窗口直到比對完成。輸出只有筆數、table identifiers 與摘要，不寫出原始 rows。此查核會在記憶體中處理本機完整 rows，不能直接作為大型 production 備份效能或 RPO/RTO 證據。

Compose object_data 的實際備份要在停止 API/worker 寫入後，將 volume 以 read-only 方式掛載到已核定備份容器，或使用 host 維運掛載的同一 storage path 再執行工具；目前 CLI 的 object source 是本機 directory，不宣稱已完成 R2 remote inventory / version restore。

## 正式 recovery 流程

1. 宣告事故範圍，停止對外寄送與付款處理，暫停 API/worker writes，保留未知 provider 結果及 outbox 狀態；不直接重送。
2. 選擇已核定備份，從獨立 evidence channel 取得 manifest hash；核對環境、schema migration revision、DB 與 object 對照、key references。加密 key 的取回需與資料分權。
3. 在隔離環境還原，確認 DB/objects checksum、native consistency、逐租戶 row counts、RLS/應用 DB role grants。工具使用 `--no-owner --no-acl`，因此正式角色、grants 與外部 secrets 必須從核定的 infrastructure 配置重新建立，不能把測試 role 當 production 權限。
4. 對 job/outbox 做 application reconciliation：pending 可按原 idempotency key 重跑；已發布 snapshot/bundle 維持版本；unknown mail/payment 先查 provider 回執，不自動重扣或重發。
5. 用隔離授權測試帳號跑登入、租戶隔離、private download、報告 snapshot、錢包 ledger rebuild、課程進度、演練取消／回執後再批准服務切回。測量實際資料缺口與恢復總耗時，才填 RPO/RTO 證據。
6. 保留前一個可復原版本；驗證正式網域、TLS、cache 與監控後解除維護。按合約政策到期刪除 backup；不能承諾備份中的已刪租戶資料立刻消失。

RPO/RTO 商業目標尚待核定。可以先評估 DB WAL/PITR、每日完整快照、immutable object version inventory 與加密異地保留，但此版本没有自動開通這些服務或宣稱已達成 SLA。

## Release 仍缺的證據

Cloudflare account 與 active Account Token 已完成唯讀驗證，KUANGUARD zone 查詢可見清單為空。KUANGUARD zone CRUD、完整原 DNS 匯出、origin TLS、NS/DS 切換、R2/Stream/Access/WAF/Turnstile 上線、真實登入/付款/郵件、production backup encryption/offsite、告警路由與正式 UAT 均未完成。`edge-policy.intent.json` 與 `monitoring/checks.json` 的存在不代表線上 provider 已套用。集中輸入位置與負責人見 `docs/activation-checklist.md`。

容器 fonts-noto-cjk 提供可重散佈 fallback；沒有自行複製 Windows DFKai-SB / Times 字型。正式指定字型、PDF embedding、DOCX/PPTX 開啟後字型與逐頁視覺 QA 需報告 release gate 通過，不能用本機 Windows 成功取代 container font QA。
