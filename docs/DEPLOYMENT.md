# 部署狀態與接續工作

本轮已在既有本機部署增量更新：Next 正式 build 服務 `127.0.0.1:3180`，API `127.0.0.1:8180`，PostgreSQL `55438`，Redis `6388`。PostgreSQL/Redis 原 volumes 與私有物件保持原位。這是 development adapters 的本機驗收，並非 Staging/Production release。

原 v1.1 Docker tags/images 與三份備份保留。Partner increment 使用獨立 tags：api/worker 為 `:partner-20260910`，internal web/public portal 為 `:partner-final-20260910`。新映像只做 network-none、無來源資料掛載的 smoke，沒有替換既有容器部署。實際 image IDs／raw source binding 與 backup/restore receipt 見 [TEST_REPORT](TEST_REPORT.md)。

## 本機接續

```powershell
uv sync --locked
pwsh -File scripts/start-local.ps1 -SkipMigrations
```

現有服務啟動器保留已占用的 ports。首次建立環境才執行尚未套用的 migration 與 seed；本輪已完成 0011，不重跑歷史 UAT 或全部 Phase。更新 `.env` 缺失的 BFF key 為本機隨機值，其他 secrets 保留。正式 standalone build 需先確認、停止本工作區的 web PID，才執行 `npm --prefix apps/web run build`，避免 Windows .next 檔案鎖衝突；不刪除整個工作區作為重建手段。

## Staging → Production

1. 核對 KUANGUARD 專用 project/account/region/budget、DB owner/app角色、queue、private storage、IdP 與精確 API origin。
2. 綁定已審查 commit、映像 digest、migration plan、備份還原結果。使用 Staging 合成帳戶，不搬入正式客戶資料。
3. 設定 shared server-only PORTAL_PROXY_SECRET、精確 origins、中央 callback 與 cloud edge。public 與 internal build/ingress 分開；Vercel 只承載 public surface。
4. 驗證 two-partner isolation、session、custom domain/TLS、Access、report/credit/provider smoke、視覺／鍵盤無障礙，再準備正式發布計畫。
5. 正式 provider/商務/安全驗收未完成，既有 Production gate 保持關閉；不得移除 gate 或把 development adapters 改名後上線。

GitHub 同步是原始碼發布，不會自動建立 KUANGUARD 公網服務。Repository 為公開；`.env`、`.local`、私有報告、restore、完整 logs 不入 Git。新版本走 CI 後再以 remote SHA readback 確認。沒有執行外部 DNS、正式 migration、付款、郵件或來源商家產品發布。

回復時可回到已驗證舊程式／映像，保留新增表與 audit，不 DROP、不重扣／重寄。若已啟用新功能或新增正式資料，先完成相容性和備份評估，不把舊 database 覆蓋到 live 服務。
