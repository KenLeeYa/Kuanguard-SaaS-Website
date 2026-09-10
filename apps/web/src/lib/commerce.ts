export const commercePaths = ["", "products", "products/ordering", "solutions", "features", "pricing", "partners", "about", "contact", "merchant/apply", "privacy", "terms", "terms/merchants", "terms/partners", "security", "solutions/restaurant", "solutions/beverage", "solutions/food-stall", "solutions/retail", "solutions/beauty"];
export const commerceTitles: Record<string, string> = { "": "數位科技、產品與平台服務", products: "產品與平台", "products/ordering": "商家點餐系統｜旗下 SaaS 產品", solutions: "數位解決方案", features: "點餐產品功能", pricing: "點餐產品收費方式", partners: "合作夥伴計畫", about: "關於 KUANGUARD", contact: "聯絡我們", "merchant/apply": "申請商家開通", privacy: "隱私權政策", terms: "服務條款", "terms/merchants": "商家服務條款", "terms/partners": "合作夥伴服務條款", security: "資料安全與信任" };
export const solutions = [
  { slug: "restaurant", name: "餐飲門市", icon: "餐", title: "尖峰時段，也能從容接單。", description: "讓顧客掃碼點餐，前場確認訂單、後場依品項出單，減少來回抄單。", flow: ["桌邊掃碼點餐", "確認餐點與備註", "出單與廚房協作"] },
  { slug: "beverage", name: "飲料店", icon: "飲", title: "甜度、冰塊與加料，一單看清楚。", description: "以品項規格與選項整理訂單，協助門市在忙碌時維持一致的製作資訊。", flow: ["選擇品項規格", "確認客製選項", "依訂單完成製作"] },
  { slug: "food-stall", name: "攤商小店", icon: "攤", title: "從一個 QR Code，開始數位接單。", description: "用簡單的線上菜單與點餐入口，逐步建立適合攤位節奏的營運方式。", flow: ["建立線上菜單", "分享點餐入口", "集中整理訂單"] },
  { slug: "retail", name: "零售商家", icon: "店", title: "商品、顧客與門市，放在同一個視野。", description: "商品展示與門市管理可先評估導入；庫存、退換貨和零售周邊需求依實際適配確認。", flow: ["盤點商品需求", "評估門市流程", "分階段導入"] },
  { slug: "beauty", name: "美業工作室", icon: "美", title: "把服務預約，安排得更有條理。", description: "預約入口與顧客經營可作為導入起點；技師排班與療程套票仍需需求評估。", flow: ["整理服務項目", "評估預約規則", "確認適用方案"] },
];
export const featureCopy = [
  ["ordering", "線上點餐", "菜單、品項與訂單集中管理，讓每一筆需求清楚抵達門市。"],
  ["qr", "QR Code 掃碼", "連接桌邊、櫃檯與外帶入口，減少重複傳達。"],
  ["reservation", "線上預約", "讓顧客先安排來店時間，門市掌握接待節奏。"],
  ["printing", "出單與廚房協作", "沿用既有出單與廚房流程，設備相容性於導入時確認。"],
  ["pos", "POS 整合", "整合門市日常作業；依使用場景與設備進行試用驗證。"],
  ["payments", "線上金流", "串接申請、合約與驗收完成後啟用，費率另依金流服務商。"],
  ["delivery", "外送串接", "保留外送平台整合入口，待合作核定與串接驗收。"],
  ["crm", "顧客經營", "從顧客紀錄與回訪需求開始，逐步建立店家的服務關係。"],
  ["multi_store", "多門市管理", "以組織和門市分工，依實際角色查看營運資料。"],
  ["analytics", "營運概覽", "以既有訂單資料整理營運結果，協助掌握日常變化。"],
];
export const messages = {
  "zh-TW": { login: "登入", apply: "申請開通", features: "功能介紹", pricing: "收費方式", partners: "合作夥伴", available: "可用 · 既有商家系統", beta: "試用中", planned: "規劃中", merchant: "商家登入", partner: "合作夥伴登入", admin: "平台管理員", customer: "資安客戶與學員" },
  en: { login: "Sign in", apply: "Apply", features: "Features", pricing: "Pricing", partners: "Partners", available: "Available in merchant product", beta: "Beta", planned: "Planned", merchant: "Merchant", partner: "Partner", admin: "Platform admin", customer: "Security customer and learner" },
  vi: { login: "Đăng nhập", apply: "Đăng ký", features: "Tính năng", pricing: "Bảng giá", partners: "Đối tác", available: "Có sẵn", beta: "Thử nghiệm", planned: "Dự kiến", merchant: "Cửa hàng", partner: "Đối tác", admin: "Quản trị", customer: "Khách hàng bảo mật" },
};
export const t = messages["zh-TW"];

export const commerceDescriptions: Record<string, string> = {
  "": "KUANGUARD 數位科技，以商家 SaaS、合作夥伴平台與企業資安服務，連接產品、資訊與人。",
  products: "探索 KUANGUARD 旗下商家點餐系統、合作夥伴平台與企業資安服務，了解適合你的產品與導入方式。",
  "products/ordering": "KUANGUARD 旗下商家 SaaS 產品，提供掃碼點餐、預約、出單與多門市管理，功能與計費依產品開通條件提供。",
  features: "了解 KUANGUARD 商家點餐產品的功能、適用情境與開通狀態。",
  pricing: "查看 KUANGUARD 商家點餐產品的公開方案、成功訂單計費與費用試算。",
  solutions: "從商家與門市、企業與團隊、專業服務夥伴的情境出發，選擇合適的數位產品與服務。",
  about: "認識 KUANGUARD 數位科技：從實際工作需求出發，以產品、平台與專業服務連接不同領域。",
  contact: "聯絡 KUANGUARD，討論數位產品導入、企業資安或合作平台需求。",
};
