import { stallOrder, studyMesh } from "./product-links";

// Public introduction only. Status and destinations were checked on 2026-09-13.
export const introduction = {
  headline: ["串起生活服務，", "開啟數位合作。"],
  description: "從餐飲、美業到學習服務，我們持續開發貼近使用需求的數位產品，並邀請各領域系統廠商，共同探索服務介接與商家曝光的合作可能。",
  productsTitle: "從實際需求出發，打造合適的數位工具",
  productsDescription: "我們以餐飲、美業與學習場景為起點，逐步發展產品與服務。各項功能及開放使用狀態，請以對應產品頁面為準。",
  domainsTitle: "讓不同領域的服務，有更多連結的可能",
  domainsDescription: "我們歡迎已開發相關系統的廠商，共同討論服務介紹、商家曝光與平台介接。以下為合作方向，實際合作內容依雙方確認為準。",
  cooperationTitle: "您專注系統服務，我們一起探索更多曝光機會",
  cooperationDescription: "若您已開發餐飲、美業、居家、交通、教育或醫療等領域的系統，歡迎與 KUANGUARD 洽談合作。我們希望保留各廠商原有的系統與服務關係，從產品介紹與服務導流開始，依需求逐步評估資料與功能介接。",
  visionTitle: "共同打造更容易被找到的生活服務入口",
  visionDescription: "我們規劃與不同系統廠商合作，讓符合合作條件並完成公開授權的商家，有機會在共同入口展示服務，供使用者探索並前往原系統使用。實際搜尋、刊登與介接功能，將依合作進度逐步評估。",
  visionPrinciples: [
    "訂閱資格與公開同意分開確認；不因商家訂閱系統就自動公開資料。",
    "以獲授權的商家公開資訊與服務連結為合作基礎，不共享顧客名單、病歷或私人學習資料。",
    "各廠商保留原有系統與服務流程，後續合作範圍由雙方確認。",
  ],
} as const;

export const ownProducts = [
  { id: "ordering", category: "餐飲數位服務", name: "攤點通｜餐飲點餐系統", status: "開放申請評估", description: "以掃碼點餐、POS 接單、廚房出單與多據點管理，協助餐飲業者整理日常營運流程。", note: "申請資格、功能及啟用時間依產品團隊確認。", href: "/products/ordering", action: "探索點餐產品", website: stallOrder.website },
  { id: "beauty", category: "美業預約服務", name: "美業工作室系統", status: "規劃中", description: "以美髮、美甲、美睫等服務情境為出發點，規劃預約安排與顧客服務的數位工具。", note: "獨立產品規劃，尚未上線；攤點通專注餐飲點餐。", href: "/contact", action: "洽詢產品規劃", website: null },
  { id: "studymesh", category: "學習／學術服務", name: "StudyMesh", status: "開發中", description: "以學習資料整理、筆記與知識管理為方向，協助建立有條理的學習流程。", note: "產品官網已公開，登入啟用仍在準備中。", href: studyMesh.website, action: "了解 StudyMesh", website: studyMesh.website },
] as const;

export const cooperationDomains = [
  { id: "food", title: "食・餐飲", description: "點餐、訂位與餐飲營運系統，探索服務入口與商家曝光合作。" },
  { id: "beauty", title: "美・美業", description: "美髮、美甲、美睫等預約系統，討論服務介紹與預約導流合作。" },
  { id: "clothing", title: "衣・服飾與生活服務", description: "洗衣、改衣、租借與零售系統，探索多元生活服務的連結。" },
  { id: "home", title: "住・居家服務", description: "清潔、維修與居家服務平台，討論區域服務介紹與需求導流。" },
  { id: "transport", title: "行・交通服務", description: "停車、租車與接送相關平台，探索交通資訊與服務入口合作。" },
  { id: "leisure", title: "育樂・課程與活動", description: "課程、活動、場館及體驗服務，討論報名與預約入口合作。" },
  { id: "medical", title: "醫療・院所服務", description: "歡迎院所資訊與掛號系統廠商洽談公開資訊及官方服務入口合作。" },
  { id: "academic", title: "學術・學習與知識", description: "學習工具、教育平台與知識管理服務，探索產品介紹與服務合作。" },
] as const;

export const cooperationModes = [
  ["系統介紹合作", "經雙方確認後，呈現產品介紹與官方服務連結。"],
  ["商家曝光合作", "規劃讓符合合作條件、且已授權公開的商家，於未來整合入口被搜尋與發現。"],
  ["技術介接評估", "依廠商提供的正式介接能力與授權範圍，討論公開資料同步或服務導流。"],
  ["專案合作", "依產業需求討論合作內容、分工、時程與維運方式。"],
] as const;

export const cooperationSteps = [
  ["聯絡交流", "了解產品、服務領域與合作需求。"],
  ["可行性評估", "確認資料授權、服務連結與可提供的介接方式。"],
  ["確認合作", "討論分工、費用、時程與維運安排。"],
  ["依約推進", "按確認的範圍安排後續介紹或介接專案。"],
] as const;

export const cooperationFaq = [
  ["一定要更換原有系統才能合作嗎？", "合作方向以保留原系統為出發點，可先討論產品介紹與服務連結，是否需要技術調整依實際需求評估。"],
  ["訂閱商家會自動出現在共同入口嗎？", "不會。規劃中的商家曝光合作，需確認刊登條件與公開授權；訂閱本身不代表同意公開。"],
  ["目前已經能在這個網站搜尋所有合作商家嗎？", "本網站目前以產品介紹與合作諮詢為主。共同入口與商家搜尋屬後續合作規劃，尚未提供的功能不會作為已上線服務呈現。"],
  ["沒有 API 的廠商可以洽談嗎？", "可以先討論產品介紹或官方服務連結合作，其他介接方式另行評估。"],
  ["合作是否需要共享顧客資料？", "目前提出的曝光與導流方向，以經授權的商家公開資訊及服務連結為主，不要求提供顧客名單。"],
  ["合作如何收費？", "依合作範圍、介接需求與維運安排個別討論，歡迎聯絡洽詢。"],
] as const;
