# KUANGUARD 執行中專案增量更新：Codex v1.0 → v1.1

版本：1.1｜日期：2026-09-10｜語言：台灣繁體中文  
適用：目前已在執行原版 KUANGUARD 官網與資安 SaaS Prompt 的 **同一個 Codex 專案與對話**。  
完整規格：kuanguard_codex_prompt.md v1.1。本增量檔可獨立交給原 Codex 執行；未變更的原版功能與驗收仍有效。

## 給執行中 Codex 的立即指令

請把本訊息視為現有 KUANGUARD 任務的新需求，**接續目前進度**。先在不破壞進行中交易、部署或遷移的一致檢查點，讀取本檔並核對工作樹、當前 Phase 與實際完成證據，然後直接實作受影響的差異。已完成且仍符合需求的部分保留；完成更新後接回原本未完成的七服務工作。

不要把本檔當作全新專案，不要重跑全部 Phase 0，不要重新 scaffold、reset/clean 工作樹、刪資料庫、重建已存在資源，或把已完成程式改成 mock。不要因新文件的預設技術與目前程式不同就整套重寫。這是增量實作命令，不只產出另一份規劃。

先簡短回報：目前 Phase、已保留成果、本次受影響項目。持續完成可執行的修改、必要測試與可審閱部署差異；真正缺少帳戶登入、正式憑證、核定預算或外部系統權限時集中記錄，其餘工作繼續。

## 1. 已由使用者決定，不要重問

| ID | 更新決策 |
| --- | --- |
| UPD-01 | QIDAIGO 訂餐系統與 KUANGUARD 資安系統由 **同一人管理**，預設同一 owner 共用既有 Cloudflare Account、Vercel Team、Supabase Organization |
| UPD-02 | 共用供應商與管理，兩產品維持獨立部署、DB Project、環境、憑證、備份、帳本、授權與背景工作 |
| UPD-03 | KUANGUARD 官網/客戶/學員 UI 目標採 Vercel；DB 採獨立 Supabase Project；API、內部 UI、報告 workers 與 Gophish 採資安專用容器 |
| UPD-04 | Cloudflare 管理 kuanguard.com 的 DNS 及適用服務；Vercel host 預設 DNS-only，admin 容器採 Tunnel+Access |
| UPD-05 | 在 admin.kuanguard.com/portfolio 加入公司總管理後台，唯讀彙總兩產品營運/待辦/費用及健康 |
| UPD-06 | 社交工程與 LMS 繼續共用 KUANGUARD 企業點數；與訂餐的交易、計費、預存款或點數獨立 |
| UPD-07 | 同一人可依明示角色操作與核定，不強制第二位管理員、不虛構第二覆核者；特定合約的獨立覆核要求仍依政策處理 |
| UPD-08 | 保留 Codex 已完成進度與正式資料，以相容、可回復的方式更新，最後接回原任務而不是停止在文件階段 |

kuanguard.com 已由使用者在 GoDaddy 購買，註冊商保留 GoDaddy。qidaigo.com / app.qidaigo.com 屬訂餐平台，不能當作資安網域或此次 DNS 變更目標。共用管理者不代表收款公司/商店已確定相同。

先前訂餐有 Next.js/React/TypeScript、Prisma、Supabase、Vercel、Cloudflare 的專案紀錄；這是盤點線索，不代表本次控制台已驗證，也不是搬用其正式 URL/key 的授權。

## 2. 必須保留的原版核心

- VA、WVA/WEBVA、SHC、PT、源碼掃描、社交工程、教育訓練 **七項首波全部納入**。年度整合方案以範圍/頻率/額度計價，不改成無限服務。
- VA/WVA/SHC/PT 由工程師到場檢測採集、公司內部後台匯入、覆核後發布。客戶只看授權結果、正式報告、時程、文字修補回覆與複測申請；沒有檢測原始檔上傳/掃描啟動 UI，直接打 API 也拒絕。
- 源碼服務首波提供內部處理/報告/複測；未核定交付方式前，不開客戶原始碼上傳或任意 Git URL 抓取。
- 社交工程是客戶自助購點、名單匯入、活動、排程與成效，整合既有 Gophish；不能被改成只有公司工程師操作。演練不收集/儲存密碼。
- LMS 在同一資安平台，企業購點派課，學員學習/測驗/證明。單獨購點可使用，不強制年度合約。
- 原始檔、未發布發現、內部成本與正式客戶交付分權；PM/派工/年度服務、複測、驗收、收款與學習進度各自狀態。
- 報告以同一核定快照產製，保留模板頁首頁尾/TOC/頁碼/表格與字型：報告中文標楷體、英數 Times New Roman；PPT 依既有微軟正黑體及26/24/18規則。Informational/None 不轉 Low；不抄歷史固定數量；複測未覆蓋不能判修復。
- 原版其他功能、實際資料與已完成驗證保留；新架構不降低 tenant/role 授權。

## 3. 在安全檢查點盤點，建立增量清單

### 3.1 先確認實際工作狀態

讀取目前 AGENTS.md、任務計畫、原 Prompt、docs、git status/diff、branch/HEAD、鎖檔、migration history、部署設定與可用服務狀態。不要輸出 secrets、完整客戶證據或以任意全機掃描找帳密。

列出哪些已完成、正在執行、尚未開始；如果有同一任務的其他 agent 正在改相同檔案/資源，先協調分工與檢查點，不同時套 migration/DNS。保留未提交變更與目前使用者編輯，不能假定 dirty worktree 可刪。

正在執行且有外部效果的工作，依該程序完成/取消/回復機制進入一致狀態，不 kill 到一半。發送結果未知先對帳，不因架構更新重送；進行中的 DB migration 完成或按既有復原機制處理後才切新設定。

產出並持續更新 `docs/update-v1.1-status.md`，最低欄位：

| 欄位 | 內容 |
| --- | --- |
| Existing progress | 當前 Phase、branch/基準 commit、已完成證據、未提交工作歸屬 |
| Requirement | UPD ID、受影響原章節/原 Phase、現況與差距 |
| Decision | 保留、局部改造、新增、需相容遷移、待外部依賴 |
| Execution | 路由/API/設定/表/遷移/資源的實際變更 |
| Validation | 已有證據可沿用部分、新增檢查及結果 |
| Rollback | 對應元件回復方式與資料影響 |
| Remaining | 具體阻礙、安全配置位置、解決後重跑項目 |

### 3.2 依現況選路徑

- **只有規劃或骨架：**直接把接下來實作導向本版架構，重用已有元件，不重新建立相同專案。
- **已有程式，尚無正式資料：**局部調整部署 adapter、環境與授權邊界；建立 KUANGUARD 專用資源與測試，不先砍原環境。
- **已有正式/重要資料或部署：**保留原服務，先在隔離環境完成相容變更和遷移演練。盤點 DB/物件/IdP/session、未結帳 ledger、job/outbox 與寄送狀態；備份可還原後才安排已授權切換。預設規格不是自動刪原資料或移轉組織的理由。
- **既有架構已符合隔離且穩定：**沿用並寫 ADR；若採用不同 UI/API framework/migration 工具，重點是行為和邊界一致，不要求只為名稱一致而全面替換。
- **帳戶或正式憑證不可用：**完成程式、設定驗證、測試、IaC plan 與待啟用清單；UI 如實顯示未連線，不偽造建置/付款/寄信成功。

切換不能造成來源與目的 DB 非受控雙寫；一次只有一個業務寫入主體。新欄位/契約先用向前相容的 expand/contract 策略；舊 worker 仍可能執行時採相容版本或 drain 後再切換。已完成 report/job、部分退款及未知寄信狀態皆要保留。

## 4. 套用共用 SaaS 與產品隔離

### 4.1 資源配置

| 層 | 共用管理 | KUANGUARD 專用資源 |
| --- | --- | --- |
| Cloudflare | 既有 Account，同一 owner | kuanguard.com zone、Tunnel、Access policy、R2 buckets/credentials |
| Vercel | 既有 Team | 官網/app Projects、部署、環境變數與 domain binding |
| Supabase | 既有 Organization | production 與非正式環境各自 Project/DB/credentials，與 QIDAIGO 分開 |
| 容器/佇列 | 可同供應商與管理工具 | FastAPI/admin、report workers、Gophish、queue、資源限制與 DB pools |
| 金流/發票 | 可同供應商及重用 adapter | 商品、訂單映射、ledger、回呼、退款與各自商店設定 |
| 監控/客服/GitHub | 可共服務與工作流程 | 各產品授權、告警、記錄、secrets 和版本發布 |

新增或重用前查 product/environment → resource ID，不照抄訂餐 Project ID、DB URL、token 或 bucket。設定檢查應在錯產品/錯環境時 fail closed；Preview 不得使用正式 secrets。工程師只使用資安應用內的職務權限，不需要新增 SaaS 控制台成員。

依 2026-09-10 Supabase 官方說明，project-scoped Dashboard roles 限 Team/Enterprise；目前是同一 owner，不構成強迫升級或拆 Organization 的理由。日後有需要限制單一產品的雲端協作者，再評估方案。

成本文件區分既有與新增 compute、儲存、影片、寄信、容器、流量及固定費分攤。新增 Supabase Project 有 compute 費，部分額度全 Organization 共用；不沿用未驗證的舊價格、不宣稱第二產品免費。已有預算與授權則執行；不足只集中列明需要的決策。

同一帳戶的欠費/停權/配額仍是共同故障範圍。使用 owner MFA/復原機制與最小範圍 service credentials，獨立輪替、備份及回復；不為單人管理邀請第二個人。

### 4.2 API 與資料庫

- FastAPI（或已存在且核定保留的核心 API）是資安業務/點數/發布唯一寫入邊界；Vercel UI/BFF 不複製帳務規則。
- Supabase 可只作 PostgreSQL；不因共用供應商強制把既有登入換成 Supabase Auth。KUANGUARD 選定的 IdP/session 契約明確，QIDAIGO 原有登入與 Google/LINE/Apple 需求不變。
- 驗證 token 簽章、issuer、audience、期限及伺服器 membership；身份採 issuer+subject，不按相同 Email 合併產品、企業或角色。
- 直接 PostgreSQL 連線不自動繼承使用者 JWT/RLS。採受信任 tenant/actor 的 transaction context、API 授權、最小 DB role 與 RLS/外鍵，測試連線池在成功/例外/回滾後無跨租戶殘留。
- 一般 API role 不具 BYPASSRLS，也不以表 owner/超級使用者查客戶資料；遷移/排程特權帳號與 runtime 分開。內部上傳也驗 employee/專案授權。
- 敏感 schema 不暴露 Data API；必要公開表才設定明確 grants/RLS。service_role/secret key 不放瀏覽器或 NEXT_PUBLIC_；views/functions 不得繞過授權，user_metadata 不作權限來源。
- 指定唯一 schema migration owner。現有 Prisma/Alembic/Supabase SQL migrations 穩定可保留；同張表不讓多套工具同時管理。若全新 FastAPI 採 SQLAlchemy/Alembic，不修改 Supabase managed auth/storage schema。
- 部署區域依資料地域需求與實測延遲配置；訂餐既有東京地區不代表新資安合約已接受。不宣稱 R2 或 Supabase 預設留台。

## 5. 修正 Cloudflare / Vercel / Access 路由

原版「所有 UI/流量均經 Cloudflare 邊界或全容器」預設由下表取代。已在運作的路由先完成相容 plan/驗證，再切換。

| Host | 目標與保護 |
| --- | --- |
| kuanguard.com、www.kuanguard.com | Vercel 官網，Cloudflare DNS-only；www redirect 由 Vercel 處理 |
| app.kuanguard.com | Vercel 客戶/學員 UI，DNS-only；應用登入、租戶授權、no-store |
| admin.kuanguard.com | 容器內部 UI，Cloudflare Tunnel+Access+應用角色；含 /portfolio |
| api.kuanguard.com | 容器 API 的限定公開客戶/學員與 webhook 路由，按需要 Proxy/Tunnel；應用/簽章授權，不被員工互動式 Access 擋住 |
| assets.kuanguard.com | 僅公開資產；私有報告不放此入口 |
| notify.kuanguard.com | 資安交易通知驗證，依實際寄信供應商 |
| sim.kuanguard.com 或核准演練網域 | 獨立事件/教育服務，不持有管理 cookie；用途與供應商授權核定後啟用 |

- DNS-only 的 Vercel host 使用其 TLS/CDN/防護；不能宣稱 Cloudflare WAF/Access 已保護該流量。Cloudflare Full(strict) 只作用在適用 Proxy 路徑，Tunnel 依其官方連線機制驗證。
- Access 以目前唯一 owner 作初始名單；日後已授權工程師可加入內部入口名單並沿用應用 RBAC，不授予 SaaS 控制台權。/portfolio 仍限 owner/指定 grant。
- admin 同源 /internal 轉到 API，後端要求 Access JWT 與應用 session/role；驗簽/issuer/audience/期限，不信任可偽造 header。公開 api host 不路由 /internal 或拒絕缺少同等驗證的存取。
- admin 的容器 origin/替代網址/Preview 不能繞過 Access；Tunnel origin 不額外公開管理 port。客戶/學員/付款郵件 webhook 與內部管理分授權。
- 若現有 Vercel admin 需要保留，先評估正式支援的部署保護/Access 代理方式並寫 ADR，完成 domain alias/preview/直接 vercel.app 的防繞過測試；不可 DNS-only 卻聲稱受 Access 保護。
- 保留 kuanguard.com 完整原始 DNS、MX/TXT/CAA/SRV，核對 NS/DNSSEC/DS/TLS，再套差異與回復方案。不要動 QIDAIGO DNS，也不要讓 IaC 接管同帳戶的所有 zone。
- Vercel/Cloudflare 敏感路由各自 no-store/bypass，報告/支付/演練不得公開快取。HSTS、憑證、callback 與現有 session 的切換影響需驗證。

## 6. 加入公司總管理後台

路由：/portfolio、/portfolio/products、/portfolio/finance、/portfolio/tasks、/portfolio/operations、/portfolio/costs、/portfolio/integrations，全部在 admin.kuanguard.com 的員工保護下。

實作產品切換、各產品健康與待辦、財務摘要、SaaS 成本/預算、connector 驗證/刷新/停用。保留原 /overview 資安作業總覽。

- 同一 owner 可被授予各產品所需管理角色，總覽權不自動等於所有客戶弱點證據/受測名單的存取權。
- 只用各產品 **受限唯讀彙總 API/adapter**，不直連訂餐 DB 或複製它的管理 key。product/environment/scope 由 connector 憑證可信綁定，請求不可自報來源提高權限。
- 先盤點已存在的 QIDAIGO endpoint；若缺少，完成契約與 adapter/測試，準備最小來源端 patch 供審閱，不自動合併、發布或修改訂餐 schema/登入/出單/費率。現有無權限時標未連線，資安其他功能繼續。
- 統一記錄 metric definition version、period/timezone、currency/unit、來源資料時間、同步時間及完整性；source timeout/過時/未連線不可顯示 0 收入或綠燈。單一來源故障不阻塞另一產品。
- 分開訂餐 GMV、平台應計/實收服務費，資安合約額/實收/退款/應收，點數購買/預留/耗用。GMV 不是平台收入；購點與耗用不重複加總。保留來源核定費率，不能在總覽改寫訂餐每單抽成或月上限。
- 只有幣別/時區/含稅方式/期間/指標口徑一致且已驗證的數字才能合併。未核定收入認列時標為營運指標，不能冒稱正式財報。
- projection 最小化、可重建、有 TTL/撤銷授權清除；不複製完整訂單、弱點、原始碼或個人名單。cache/search/export/key 都帶產品範圍。
- 退款、改訂單、調點、出單、發布報告回到來源產品的既有流程；公司總覽首波不做跨產品寫入。外部深連結用核定 host，不以 URL 分享 session。
- 公司總覽功能需具備真實可操作狀態；已授權來源連線可用則實接驗證，未有來源時只在開發用合成資料驗證，正式不顯示 mock 營收。

## 7. 單人營運與專用處理服務

### 7.1 同一管理者

保留職務與操作紀錄，同一已驗證 actor 可兼 owner、PM、工程師、財務、覆核/發布角色，依實際授權配置。單人管理不代表所有現場工程師只有你，也不要求自動給 owner 所有客戶原始證據。

一般單人 QA→核定→發布與財務流程可執行，明示同一 actor/時間/理由。需要時對高風險操作重驗身分、顯示差異預覽與稽核，不以新增另一個假帳號滿足覆核。若特定合約要求不同人獨立覆核，按真實政策處理，不為方便繞過，也不阻擋其他不受此條件限制的工作。

### 7.2 報告與演練隔離

資安 report/解析/源碼 workers、Gophish 與訂餐 API/出單各自 queue、連線池與資源配額。重工作不塞入單次 Vercel Function，不讓它占滿訂餐服務 CPU/記憶體。

訂餐交易通知、資安通知、演練至少分 sender/profile/queue/額度；演練用獨立帳號/寄信服務，確認允許用途，不能借用訂餐通知帳號/網域。子網域只部分隔離根域聲譽；另購演練網域仍按既有授權流程。

R2 同 Account 但分產品 bucket 與範圍限制的 S3 credentials，私有報告不公開；Stream 課程播放仍先驗 enrollment。公司總覽/共同監控不讀受測名單或弱點原文。

### 7.3 帳務維持正確

社交工程/LMS 在資安平台共錢包，訂餐另計帳。append-only ledger、預留/耗用/回沖、點數效期、冪等與補償維持原規則。

共用支付供應商不等於直接共 merchant。確認實際收款主體與用途；如共 merchant，簽章後仍按可信 product/order mapping 對帳與入點，不能跨產品回呼加點或重複退款。

## 8. 執行順序與必要驗證

以此表加入當前任務計畫，不取代原本所有 Phase。每一項先比對已有完成證據，符合者標保留，只對差異實作。

| 更新階段 | 工作與完成條件 |
| --- | --- |
| U0 檢查點 | 保存目前進度/工作樹、協調進行中任務，產出 UPD 差異表 |
| U1 邊界 | 共用帳戶/產品資源清冊、成本假設、單人角色、DB/API/secret 邊界與 ADR |
| U2 局部改造 | 受影響的設定/UI/API/DB/worker/route；若有資料遷移，先完成相容與還原演練 |
| U3 公司總覽 | 真實總覽路由、唯讀 adapters、財務口徑、未連線/過時/錯誤狀態 |
| U4 驗證與切換 | 受影響測試、可審閱 infra/DNS 差異、按既有授權啟用與回復證據 |
| U5 接回進度 | 更新 traceability/Phase 狀態，接續未完成七服務直到可執行工作完成 |

**有變更才補驗證，沿用有效證據；不為更新 MD 重跑全部掃描或已通過的無關測試。** 但正式上線仍須符合原七服務共同 release gate。

最低新增驗證：

1. 跨產品/租戶 token、URL、scope、bucket/DB credentials 互換被拒；相同 tenant ID 不串資料。
2. DB role/RLS/context 與 pool 清理，含例外/回滾；Data API/view/function 無授權旁路。
3. Cloudflare/Vercel 路徑與 TLS 正確；admin 直接 origin/alias/Preview/公開 internal 不繞過 Access，客戶與 webhook 正常。
4. 同一 owner 能完成既有角色流程且稽核真實；特定獨立覆核政策未被關閉。
5. 公司總覽真實資料/未連線/過時/撤銷/timeout 皆正確；財務口徑不將 GMV 或點數購買/耗用重複計收入。
6. 社交工程/LMS 共錢包，訂餐不能抵扣；錯產品支付回呼不入點；既有 pending/unknown 寄送狀態保持可對帳。
7. 部署/遷移 idempotent，重跑更新不多建 Project/bucket、不重複扣點/寄送；有回復證據。
8. 代表性背景負載驗證在隔離測試環境執行，不對訂餐正式環境做壓測；資安工作不能占用訂餐 queue。
9. 七項服務、客戶無掃描上傳、工程師後台匯入、Gophish 與 LMS 自助路徑無退化。保留原報告字型/統計及複測口徑。
10. 若沒改動 QIDAIGO，展示它沒有本次寫入/部署變更的證據；無存取權則標未驗證，不假造 git diff 或宣稱測過其正式出單。

## 9. 最終交付與回報

直接更新現有 repo 的規格/文件並實作，不建立另一套並行真相。完整 Prompt v1.1 如已附上則按其 CORE-01～17、QA-01～32 同步；若只取得本檔，將 UPD-01～08 合併進目前可讀的 v1.0 需求矩陣，不因缺另一份檔案停工。

至少交付：
- 已修改的程式、必要 migrations、部署與型別化設定驗證、鎖檔及受影響測試。
- docs/update-v1.1-status.md、docs/shared-saas-inventory.md、docs/product-isolation.md。
- docs/shared-saas-costs.md、docs/portfolio-integration.md、更新後 route-map/ADR/traceability。
- docs/activation-checklist.md：只列真正缺少的帳戶/憑證/預算/合約/來源 API，一次集中；管理者人數與共用架構已定，不再詢問。
- 各部署/資源/連線的實際狀態：保留、已修改、已測、已部署、待啟用、未驗證各自區分。

向使用者回報：**保留了什麼、增量改了什麼、如何驗證、尚缺哪些必要設定、已接回哪個原 Phase。** 不能把更新文件稱為整個平台已遷移或上線。不要要求使用者分批再貼 Phase；繼續完成剩餘已授權工作。

## 10. 官方依據

查核基準2026-09-10；實際操作再核對當期官方能力、穩定版本、帳戶現況與預算。

- [Cloudflare 帳戶與 Zone](https://developers.cloudflare.com/fundamentals/concepts/accounts-and-zones/)
- [Cloudflare R2 範圍權限](https://developers.cloudflare.com/r2/api/tokens/)
- [Cloudflare Access 內部應用](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/)
- [Vercel 多 Project](https://vercel.com/docs/projects/overview)
- [Vercel 與反向代理](https://vercel.com/docs/security/reverse-proxy)
- [Supabase 組織與 Project 計費](https://supabase.com/docs/guides/platform/billing-on-supabase)
- [Supabase 控制台權限與方案](https://supabase.com/docs/guides/platform/access-control)

**現在先讀取實際專案進度，套用本次增量更新，然後接續原本任務。**
