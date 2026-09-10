# 三傑科技接入狀態

配置檔：[config/partners/megaprotek.json](../config/partners/megaprotek.json)。三傑採一般 Partner 架構，沒有獨立 fork、專屬 backend 或 hard-coded tenant ID。

本機 fixture 已建立 `megaprotek` Partner、獨立錢包、五種職務、合成客戶及個人專案 grants。`portal.megaprotek.com.tw` 已登記為 PENDING。這是技術接入範例；Partner 合約、正式成員與 DNS 所有權尚未核定，不能稱為已正式上線的合作夥伴。

可從本機 `/partner/login?partner=megaprotek` 開始，選「三傑科技・示範管理員」。第二合成 Partner 使用 `example-partner`，已加入互相隔離測試。真實 custom hostname 的 HTTP Host 測試現為 404，符合未驗證不可登入規則。

正式接入順序：指定 Partner 類型與合約／客服資訊 → 綁定經 IdP 驗證的實際成員 → 開啟核定功能 → 上傳合法 logo → 設定正式 portal target → 產生一次性 TXT → 三傑 DNS 管理者設定 → 驗證所有權與 TLS → 中央登入／報告下載／點數流程驗收。

DNS 和 credential 的具體負責事項集中於 [MANUAL_ACTIONS_REQUIRED](MANUAL_ACTIONS_REQUIRED.md)。不得把合成 customer／wallet／身份複製到正式環境。
