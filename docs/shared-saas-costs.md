# 共用 SaaS 成本與啟用預算

查核：2026-09-10。貨幣以官方 USD 公開價作估算，未含適用稅額或匯率；現有實際 invoice、折扣、用量餘額尚未取得。共用 provider 與同一 owner 已核定，新增付費資源的預算尚未核定，本次新增 Projects／訂閱／付費服務為 0。

## 既有固定費与本次新增費

| 項目 | 既有／新增如何分開 | 本次查核與估算 |
| --- | --- | --- |
| Vercel Team | 保留既有 Pro Team 固定費；本次不新增 owner 席位。KUANGUARD deploy/build/runtime/CDN 用量獨立歸集 | Team API 回覆 Pro；官方 Pro 公開起價 US$20/月與 US$20 usage credit。新 Project 不代表新用量免費，不能先假定既有 credit 尚有餘額。[Vercel pricing](https://vercel.com/pricing) |
| Supabase Org | 保留既有 Pro Org 訂閱；本次新資安 Projects 各產生 compute | live get_cost 對確切 Org 回覆單一新 Project amount 10 / monthly；Production＋nonproduction 基礎 compute 約 US$20/月，仍須核定 |
| Supabase 用量 | 各專案 dedicated compute；某些 egress/Auth/storage 額度在 Org 跨產品共用 | 每個月 Org 的 US$10 compute credit 只有一份；已有三個 Projects 的占用需按帳單確認。不能把每個產品各減 US$10。[Billing](https://supabase.com/docs/guides/platform/billing-on-supabase) |
| 容器／queue | 資安 API/admin/report/Gophish/queue 自有 CPU/RAM/連線池／volume | 供應商、地區、最低資源與預算待核定；目前沒有可用正式报价，保持 unknown |
| Cloudflare | 現有 Account 控制共用；zone/Access/相關產品依實際方案與使用量歸屬 | Account plan / Access capacity 尚未 readback；不填 0，不先購買升級 |
| 金流／發票／郵件 | 與訂餐分 product/order/sender profile；演練用途另核定 | 商店、服務與授權名單未定，手續費／每封價格 unknown；本次沒有寄送、交易或採購 |

Supabase Micro 公開價 US$0.01344/小時，730 小時約 US$9.81，每個新 Project 各計。兩個 Micro 的 gross compute 約 US$19.62/月，live quote 四捨五入為約 US$20；Small 約 US$15/月／Project。Compute 不受 spend cap 自動涵蓋，不能靠開啟 spend cap 承諾封頂。既有 Org 固定費不重複算作新產品專案費。[Compute 計費與 credit](https://supabase.com/docs/guides/platform/manage-your-usage/compute)

新 Project 的 live quote 記錄在 `infra/evidence/shared-saas-inventory-20260910.json`。尚未呼叫 create_project 或 confirm_cost；正式開通需以這個具體 recurring compute 成本與主機／地域選項集中確認。這個待決策不阻擋本機程式、plan 與既有測試。

## 儲存、影片與流量估算公式

| 使用項 | 查核單價 | 預算處理 |
| --- | --- | --- |
| R2 Standard storage | US$0.015/GB-month；Class A US$4.50/百萬 requests；Class B US$0.36/百萬 requests | 先記 KUANGUARD bucket bytes / operations，再套用 Account 真正剩餘免費額度；不能複製一份免費額度給每個 bucket |
| R2 internet egress | R2 直接輸出不收 egress 費；其他串接服務可另計費 | API proxy / container / Vercel 的費用仍需獨立計算 |
| Stream storage | 每 1,000 分鐘容量 US$5/月，按容量區塊預購 | 只按合法教材長度估計，未購買 |
| Stream delivery | 每 1,000 delivered minutes US$1 | 以全部學員的實際觀看分鐘加總，不按影片檔案個數估算 |

以上來源：[R2 pricing](https://developers.cloudflare.com/r2/pricing/)、[Stream pricing](https://developers.cloudflare.com/stream/pricing/)。R2 Infrequent Access 有 retrieval 與最低保留期間等不同條件，這個範例只估 Standard。

假設示例：1,000 分鐘 Stream 容量與每月 10,000 分鐘播放，影片估 US$15/月；50 GB R2 Standard 的純 storage gross 為 US$0.75/月，另加 operations。這些是假設用量，不是現有耗用、整案總價或已核定预算；各 provider 的剩餘 credit 只能經實際帳單扣抵。

## 成本分攤與告警

保留 invoice 的 provider/account/product/environment/resource ID、billing period、currency、含稅口徑與 usage units。可直接歸屬的 compute、buckets、Stream、寄送與容器費直接歸產品；共同固定費先標「待核定分攤」，不要任意 50/50 生成正式帳務。

portfolio 的費用是營運 projection；未知、過時或未連線維持 unknown/stale，不顯示 0。付款單据未確認時不宣稱已付清。預算警戒、停止新增資源與追蹤责任人要依核定值配置，不靠自動購買解決超額。

仍需集中決定：兩個 KUANGUARD Supabase Projects 的 recurring compute、資安主機／地區／容量、R2/Stream 使用預算、演練寄信供應商用途與額度。無需再詢問是否共用 owner / Team / Org，也不為單人管理增加 Dashboard 協作者或強制升級 Team。
