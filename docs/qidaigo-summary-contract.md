# QIDAIGO 唯讀摘要來源契約

狀態：待來源端審閱與部署。此文件和 `samples/portfolio/qidaigo_summary_route.proposal.ts` 僅存在KUANGUARD workspace，沒有套用或發布到QIDAIGO。

2026-09-10唯讀盤點見 `infra/evidence/qidaigo-readonly-baseline-20260910.json`。來源checkout已髒且為detached HEAD，保留其現況。已找到 `src/lib/admin-billing-data.ts` 的 getAdminBillingOverview，內含以UTC月初計算的monthlyInvoiced及monthlyCollected，也包含pendingRequests/pendingPayments完整關聯物件；不得將這個return直接傳給公司總覽。merchant dashboard有店家scope，不能拿來當整產品owner aggregate。有限的src/app/api盤點沒有找到適用的受限portfolio endpoint。

建議新增單一 `GET /api/portfolio/summary`，從現有來源DB在來源端進行allowlisted aggregate，只回傳下面schema。不能更動原schema、登入、出單、費率、月上限，不能在KUANGUARD直連QIDAIGO DB。既有檔案或路由若不相容，應先提交最小來源PR審閱，不自動套用本proposal。

認證使用專用短效唯讀JWT（HS256）。必要claims：iss=qidaigo-summary、aud=kuanguard-portfolio、sub=portfolio-readonly、jti、iat、exp、product=qidaigo、environment、scope=portfolio.summary.read、tenant_scope。來源必須查核grant仍active、允許的環境/範圍與到期；不得僅decode未驗證JWT或接受請求自報product。KUANGUARD也再次驗證相同綁定。

Response Content-Type為application/json，Cache-Control:no-store。回傳 `X-Portfolio-Timestamp`（Unix秒）與 `X-Portfolio-Signature`（hex HMAC SHA256）；輸入為 `timestamp + "\n" + request X-Portfolio-Nonce + "\n" + exact response body bytes`，使用獨立至少32字元secret。簽章前先建好最終JSON字串，禁止簽完後改序列化。

```json
{
  "schema_version":"portfolio.summary/1",
  "product":"qidaigo",
  "environment":"production",
  "scope":"portfolio.summary.read",
  "tenant_scope":"source-approved-owner-scope",
  "grant_id":"readonly-grant-id",
  "source_at":"2026-09-10T06:00:00Z",
  "complete":false,
  "synthetic":false,
  "metrics":[{
    "key":"platform_fees_received",
    "value":null,
    "unit":"minor_currency",
    "currency":"TWD",
    "tax_basis":"unknown",
    "definition_version":"qidaigo.platform_fees_received/1",
    "period_start":"2026-08-31T16:00:00Z",
    "period_end":"2026-09-10T06:00:00Z",
    "timezone":"Asia/Taipei",
    "measurement":"flow",
    "verified":false
  }],
  "health":"unknown",
  "tasks_open":null,
  "tasks_overdue":null
}
```

允許metric keys僅gmv/platform_fees_accrued/platform_fees_received/refunds，definition_version必須對應 `qidaigo.<key>/1`；完整摘要需具備四項，缺值保留null/verified=false或complete=false。禁止傳出order/payment/customer/user原始資料、商店名稱、Email、電話、任意連結、管理session或credential。回應大小上限128KiB。

monthlyInvoiced是否可對應platform_fees_accrued、VERIFIED付款是否包括退款/沖銷、含稅方式及來源核定期間需要財務/來源owner確認；不能直接把既有UTC月數字貼上Asia/Taipei標籤。GMV與平台實收服務費不能加總，總覽不改來源抽成或上限。已知無法核定的指標先回傳null。

來源release gate：source authentication/grant revoked測試、跨scope/product/environment測試、四項金額與期間對帳、無個资schema測試、no-store、大小/timeout、簽章nonce與時間窗口測試；由來源原有CI與部署流程完成。KUANGUARD30項fake transport驗證不等於來源端這些驗證已完成。
