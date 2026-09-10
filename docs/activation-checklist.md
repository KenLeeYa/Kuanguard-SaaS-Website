# 集中啟用清單

2026-09-10 資安稽核補充：此表列外部帳戶／權利／決策，**不代表所有 provider 程式已完成**。仍需實作的 Gophish、影片／課程上架、支付／發票、R2、企業 onboarding、公平排隊與外部監控，集中見 [SECURITY_PHASE_STATUS 的 ENG-01～07](SECURITY_PHASE_STATUS.md)。原帳戶／方案／價格 readback 是歷史收據，正式動作前需重新核實；本輪沒有變更遠端資源。

更新：2026-09-10 v1.1。單一 owner 共用既有 Cloudflare Account / Vercel Team / Supabase Org 已核定；三個管理範圍均已 live readback，Cloudflare Account Token active，Vercel／Supabase 方案為 Pro。下列項目不阻擋本機實作，但目前不能宣稱正式七服務上線。提供秘密時使用 secret manager / 環境配置，不貼入 repo、issue、聊天或測試輸出。已完成本機開發的部分不需逐 Phase 再次批准。

| ID | 目前缺少或待核定 | 負責人 | 安全配置／輸入位置 | 完成後重跑驗證 |
| --- | --- | --- | --- | --- |
| ACT-01 | Cloudflare KUANGUARD 專用 zone／限定 zone scope；目前查詢可見清單為空 | 既有帳號持有人＋維運 | Account b1c70202652cd3b77dfec70e5463785f 與 active Token 已驗證；private/desired.json 補實際 zone ID | inspect target readback、完整分頁匯出、plan |
| ACT-02 | 原權威 DNS 的完整匯出、子域委派、parent DS 與候選區逐筆對照 | GoDaddy／DNS 管理者 | infra/cloudflare/private/authority-proof.json ＋加密備份 | 完整性覆核、MX/TXT/CAA/SRV/NS preserve 測試、fresh plan |
| ACT-03 | 正式容器主機、地區、預算、供應商實際 origin、TLS 與回復版本 | 負責人＋維運 | 主機 secret manager／環境設定；desired records 使用實際值 | immutable release build、origin TLS、應用 smoke、rollback drill |
| ACT-04 | 確切 DNS diff 授權、Cloudflare assigned NS、GoDaddy 必要 2FA／NS/DS 操作 | 網域持有人 | GoDaddy DNS / Nameservers；由 inspect 提供真實 NS | 各權威 NS＋兩解析器、parent DS chain、zone active、TTL 觀察 |
| ACT-05 | Cloudflare plan 能力、WAF/rate limits、Turnstile、Access employee policy、origin 防直連 | 維運＋資安 | edge-policy.intent.json 覆核後配置實際 account 資源 | app 不被員工 Access 擋住、origin JWT、webhook 無互動 challenge、敏感 cache bypass |
| ACT-06 | R2 bucket、地域契約、生命周期、短效 upload/download、Stream 正式帳號 | 維運＋法務／業務 | 私有／公開 bucket 分開，S3/Stream 憑證分環境 | 跨租戶 private download、signed playback、CORS、multipart/finalize、公開 bucket 無私有資料 |
| ACT-07 | 企業 IdP／OIDC/SAML 設定、redirect allowlist、MFA policy、員工名單 | 租戶管理者＋維運 | IdP console／secret manager；不使用 development profile 登入 | 真實 login/logout/callback、MFA、停權與支援權到期 |
| ACT-08 | 正式支付／發票供應商、商店資格、預付點數政策、退款及稅務核定 | 財務＋商店持有人 | provider secret manager／版本化 billing policy | sandbox signature/金額/幣別/乱序/退款驗證，再做核准正式小額測試 |
| ACT-09 | 通知與演練寄送分流、用途許可、核准測試信箱／名單、寄送額度 | 業務＋活動授權者＋維運 | 獨立 mail adapter 設定及 allowlist | 指定信箱往返、SPF/DKIM/DMARC、unknown outcome/bounce/取消對帳 |
| ACT-10 | 既有 Gophish 最新原始碼／版本、合法使用權與正式連線 | 系統持有人 | 獨立私有 repo/受限 API；key 不下發 browser | 真實 adapter contract、無密碼收集、accepted-after-crash 與事件對帳 |
| ACT-11 | 七服務合法去識別樣本、正式模板、核定字型與輸出對照 | 工程／覆核／內容權利人 | 受限樣本與模板庫；不得搬原公司品牌或統計 | 七服務 initial/retest、DOCX/PDF/PPTX/XLSX 逐頁 QA 與 snapshot 數字一致 |
| ACT-12 | 合法課程／教材／題庫／字幕、課程單價、完課政策及企業點數政策 | 教材權利人＋營運 | 管理後台版本化上架與政策設定 | 真實影片與字幕、首次啟動扣點、續看、測驗、證書及補救派課 |
| ACT-13 | 法定公司資訊、商標／Logo、地址、客服窗口、合約／資料保存條款 | 公司負責人 | 品牌／政策管理設定 | 正式文案／聯絡資訊／合約覆核；取消示範與未核定主張 |
| ACT-14 | Production 備份加密、異地保管、key recovery、RPO/RTO、R2 object version inventory | 維運＋資料責任人 | 分權 secret manager；加密備份目的地；離站備份 | 正式規模 DB＋完整 objects 還原、權限重建、jobs/outbox 對帳與計時 |
| ACT-15 | 監控 scheduler、on-call destination、成本／速率／容量阈值 | 維運＋負責人 | infra/monitoring/checks.json 對接已核准監控 | 故障注入、告警去重、無敏感內容、實際通知到授權窗口 |
| ACT-16 | 正式遷移來源、獨立覆核、UAT、七項共同 release gate | 公司負責人＋QA＋資料持有人 | 版本化 release / migration receipts | 權限負測、七核心 E2E、資料遷移與 rollback、正式環境拒絕 demo seed |
| ACT-17 | 資安專用 Production／nonproduction Supabase Projects 與新增 compute 預算 | 同一 owner＋維運 | 已驗證 Org urxujyhcggjgwsjtleys；新 Projects 各自 secrets；不可用 QIDAIGO IDs | 新 Project 約 US$10/月各一，兩個約 US$20/月另計 usage；核定後建置/回讀與 isolated migration/RLS/pool test |
| ACT-18 | KUANGUARD 專用 Vercel public / customer Projects、實際 domain targets、Preview 隔離 | 同一 owner＋維運 | 已驗證 Team team_MMfsiG94K9Zy3e6w7Ccc9xY4；產品專用 Project/environment | apex/www/app DNS-only、Vercel redirect、no-store、Preview 無 production secrets、admin 不從 Vercel 繞過 Access |
| ACT-19 | QIDAIGO 受限 summary API、source side contract patch 審閱／發布與獨立 connector grant | 同一 owner／來源維護者 | docs/qidaigo-summary-contract.md；portfolio connector secret manager | product/env/scope JWT、response integrity、timeout/stale/revoked；不直連訂餐 DB、不修改費率或出單 |

一般單人 QA／核定／發布可由同一真實 actor 依明示角色執行；ACT-16 的獨立覆核只依特定合約或正式 release 政策，不要求建立假第二管理員。source API 與來源 patch 未啟用時 QIDAIGO 明示未連線，其他資安流程持續執行。

本機原65表備份、v1.1的67表備份繼續保留；接續工作後最新 PostgreSQL＋objects 實際還原為80張表、811 rows、36 objects，逐表筆數與原生 JSON digest及檔案 checksum相同。最新證據位於 `infra/evidence/backup-restore-complete-20260910.json`；正式異地／加密復原與 worker redrive 仍依 ACT-14 驗證。
