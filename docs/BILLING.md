# 商家計費投影與 Partner 點數

網站從 `product_registry.pricing` 讀取公開方案，以整數 minor units 表示：TWD 100 = 每筆成功訂單 NT$1；monthly_fee_minor=0、buyout_fee_minor=0。設定可由明示 platform admin 以 expected_version 更新並留下 audit，前端沒有固定費率常數。`charge_enabled=false`，價格計算器只是估算。

訂單建立／付款狀態、成功訂單定義、去重、UsageEvent、PlanVersion、退款調整與 invoice 都由既有商家產品 billing domain 負責。本平台 `excluded_states=[failed,cancelled,refunded]` 是方案投影，不是第二套實際扣款邏輯。網站設定不得直接啟用來源產品收費。上線前須由來源產品發佈版本綁定成功訂單 policy_reference、合約、稅務、退款及免收費狀態；金流、設備和第三方服務費另列。

Partner credit allocation 沿用既有整數 FEFO 錢包。在同一 PostgreSQL transaction 依序鎖 Partner/客戶，檢查歸屬、授權、可用數量、用途與有效期。來源新增 allocate-out entry，客戶取得相同用途／期限的新 lot，兩端以 immutable allocation receipt 關聯。沒有修改、覆寫歷史交易或創造額外可用點數。

Request 帶 idempotency key；同 key 同 payload 回既有結果，不重扣。不足、凍結、外部客戶、未授權角色或不同 payload 重放會被拒絕。來源 summary 與 reconciliation 單獨列 allocated，以保持原 lot 守恆。

只有 Partner admin/finance 可分配點數。分配不是購點或外部付款；退費／重新分配須沿用核定對帳流程，不刪除 ledger。Commission 支援六種模型的 schema，但計算、結算、撥款全未啟用，不能與已可用的 credit allocation 混稱完成。

原資安服務點數與權利政策保持有效，見 [billing-policy](billing-policy.md)。
