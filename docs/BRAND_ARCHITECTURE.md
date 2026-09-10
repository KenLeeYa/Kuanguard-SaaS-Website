# 品牌與產品邊界

| 入口 | 定位 | 本輪狀態 |
| --- | --- | --- |
| kuanguard.com | 點餐、QR、預約、出單及商家營運 | 本機官網完成 |
| app.kuanguard.com | 既有商家產品入口 | 本機 bridge；来源 domain/SSO 尚未啟用 |
| partner.kuanguard.com | N 家 Partner 共用平台 | 本機角色與流程完成 |
| portal.megaprotek.com.tw | 三傑科技 Partner 品牌 | 設定映射 PENDING，沒有正式 DNS/TLS 啟用 |
| auth.kuanguard.com | 中央驗證 | broker 本機驗證；正式 IdP 待設定 |
| admin.kuanguard.com | 平台與資安內部工作台 | Access 邊界保留；尚未公網部署 |

商家功能目錄來自 `product_registry`：ordering、QR、reservation、printing、multi_store、analytics 為來源產品既有能力；POS/CRM 標示 beta，payments/delivery 標示 planned。這些是程式盤點後的產品目錄，不是設備、金流、外送合作或正式環境驗收證明。網站不展示虛構客戶數、客戶 logo、認證或合作已生效宣稱。

首頁功能、五個產業頁、價格頁、Partner 招募與聯絡表單使用原創中文。畫面流程插圖標示操作示意。零售和美業說明適配範圍，不宣稱已具完整庫存、療程或排班系統。

Partner branding 使用獨立公司名稱、合法文字、支援聯絡資訊、主色、logo、favicon 與 footer。中央登入頁保持平台驗證身份；不以一個 Partner 的身份包裝所有租戶。三傑是首個配置範例，不建立專用 fork。

前端採繁體中文，保留 zh-TW/en/vi 訊息字典結構；英文與越南文全站翻譯尚未完成。商家與 Partner 條款分開，法律頁目前為待核定草案。
