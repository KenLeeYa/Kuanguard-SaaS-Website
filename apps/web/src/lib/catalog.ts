export const services = [
  { code: "VA", slug: "va", name: "主機弱點檢測", en: "Vulnerability Assessment", mode: "工程師交付", description: "盤點主機與服務的弱點，讓每一項修補都有可追溯的起點。", scope: "主機、作業系統、網路服務與已核定 IP 範圍", preparation: "確認資產清冊、到場時段、檢測授權及必要帳號。", deliverables: ["資產覆蓋與檢測結果", "分級弱點與改善建議", "正式報告與複測追蹤"] },
  { code: "WVA", slug: "wva", name: "網站弱點檢測", en: "Web Vulnerability Assessment", mode: "工程師交付", description: "從網站功能、路徑與角色，整理可理解、可執行的改善清單。", scope: "網站、API 路徑及合約指定使用者角色", preparation: "提供測試環境、核定 URL 範圍、角色帳號與排除時段。", deliverables: ["網站範圍與路徑覆蓋", "AppScan 匯入與人工覆核", "初測及複測比較"] },
  { code: "SHC", slug: "shc", name: "系統安全健診", en: "Security Health Check", mode: "工程師交付", description: "以設定、權限與證據檢視環境，找出日常維運可改善的細節。", scope: "伺服器、帳號權限、備份及已核定雲端檢核項目", preparation: "確認設備與基準版本，準備唯讀檢視權限及現場窗口。", deliverables: ["檢核基準與證據狀態", "符合、不符合及證據不足", "改善優先順序與追蹤"] },
  { code: "PT", slug: "pt", name: "滲透測試", en: "Penetration Testing", mode: "工程師交付", description: "在明確授權範圍內，由工程師驗證攻擊路徑與實際影響。", scope: "已授權標的、API 安全與人工驗證情境", preparation: "簽認測試規則、停止條件、緊急聯絡方式與測試窗口。", deliverables: ["人工驗證與攻擊路徑", "遮罩證據與影響說明", "技術覆核、報告與複測"] },
  { code: "SOURCE", slug: "source-code", name: "源碼安全檢測", en: "Source Code Security", mode: "工程師交付", description: "將程式碼檢測結果轉為開發團隊可以處理的修補與覆核流程。", scope: "SAST 結果；SCA、SBOM、Secrets、容器與 IaC 依核定能力選配", preparation: "先確認程式語言、工具版本、來源交付方式及保存期限。", deliverables: ["SARIF 結果匯入", "規則、路徑與誤判覆核", "版本化報告與複測"] },
  { code: "PHISHING", slug: "phishing", name: "社交工程演練", en: "Security Awareness Simulation", mode: "線上自助", description: "用受控活動與教育頁，觀察風險指標並銜接補救訓練。", scope: "已授權受測群組、核准模板、教育頁及寄送窗口", preparation: "確認企業管理权、受測範圍、點數與已啟用寄送管道。", deliverables: ["活動、群組與排程管理", "事件來源及指標口徑", "回報率與補救訓練"] },
  { code: "TRAINING", slug: "training", name: "線上教育訓練", en: "Security Awareness Learning", mode: "線上自助", description: "從企業派課到員工完課，把資安觀念帶回每天的工作。", scope: "核定課程、企業學習計畫、個人與部門派課", preparation: "確認學員、課程授權期限、適用點數與年度梯次。", deliverables: ["章節學習與教材", "伺服器驗證測驗", "完課紀錄與證明"] },
] as const;

export const serviceName = (code: unknown) => services.find(s => s.code === code)?.name || String(code || "未指定");
export const publicPaths = ["", "services", ...services.map(s => `services/${s.slug}`), "plans/annual-security", "courses", "pricing/credits", "request-quote", "resources", "trust", "about", "contact", "legal/privacy", "legal/terms", "legal/credits", "legal/acceptable-use", "legal/data-processing"];
