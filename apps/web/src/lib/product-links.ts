export const stallOrder = {
  website: "https://qidaigo.com",
  login: "https://app.qidaigo.com/login",
  apply: "https://docs.google.com/forms/d/e/1FAIpQLSf859kVKh77cjNjpS26HWNqFdN851UdOQ6htlJUc9pgBlBBLw/viewform",
} as const;

// Only verified public destinations belong here. Unreleased platforms have no login URL.
export const platformEntries = [
  { id: "ordering", name: "攤點通｜餐飲點餐系統", description: "掃碼點餐、POS、廚房出單與多門市管理。", details: "/products/ordering", login: stallOrder.login },
  { id: "partner", name: "合作夥伴平台", description: "平台尚未開放，合作需求可先與我們聯繫。", details: "/partners", login: null },
  { id: "security", name: "企業資安平台", description: "平台尚未開放，資安服務可先洽詢。", details: "/services", login: null },
] as const;

export function publicDestination(path: string): string | undefined {
  if (path === "merchant/apply") return stallOrder.apply;
  if (path === "merchant" || path === "login/merchant") return stallOrder.login;
}
