# Architecture decision records

## ADR-001：保留現有 Next.js + FastAPI + PostgreSQL

v1.1 更新部署配置，不重寫已驗證資料流。UI 透過同源 `/api` 代理 API；FastAPI 是唯一業務寫入主體。共享管理帳號不代表共享 product resources。沒有 Supabase/本機雙寫。

## ADR-002：私有入口與應用授權分層

Vercel public surface 拒絕 admin aliases、internal API 與編碼／Host 繞路；獨立 gateway 只列 public API allowlist。admin gateway 驗證 Access JWT 並保留可信 Host；FastAPI 再驗 cookie session、有效 server membership、tenant、project grant 和角色。Access、Host、UI 隱藏均不能取代 app auth。

## ADR-003：核定 snapshot 為交付事實

原始來源仍可追溯，客戶只讀 publication projection。報告 worker 依快照產五格式並核對 checksum；更正 append 新 snapshot/publication。當次來源排序採 `import.commit` 稽核時間；VA 最近核定提交的 CSV 整份優先，來源差異明列。SHC 證據不足不算通過；SARIF 缺規則執行或範圍證據不推論修復。

## ADR-004：交易以資料庫為主

DB transaction 與 tenant advisory lock 將 idempotency、reservation、ledger 和工作建立一併提交。Redis 目前保留但不承擔工作真相；DB polling 可以在 queue cache 不可用時恢復。worker claim token、lease renewal、fenced completion 防止舊執行者覆蓋新結果。尚未宣稱正式寄送 exactly-once。

## ADR-005：明示多角色的同一人

owner 只是 Portfolio 權限；PM／engineer／reviewer／finance 與 project grant 必須各自存在。一般合約可由同一 actor 覆核；特定獨立覆核政策在排程、覆核、報告建立及發布重查。所有紀錄保存實際 actor，不產生假覆核人。

## ADR-006：正式啟用採共同 gate

程式與 sandbox 可以先實測，正式環境設定仍 fail closed。取得真實 credentials 後還要完成 provider adapter、模板與正式 UAT，不能只把 `PRODUCTION_RELEASE_APPROVED` 改成 true。沒有把缺少的七核心項目宣稱成未來擴充。

CI Actions 配置依 [Astral 官方 GitHub Actions 文件](https://docs.astral.sh/uv/guides/integration/github/) 及 [setup-node 官方文件](https://github.com/actions/setup-node) 查核；使用 lockfiles。上述線上內容於 2026-09-10 經 AnySearch 取得。遠端 CI 尚未執行。
