import { publicPaths } from "./catalog";
import { commercePaths } from "./commerce";

export const websitePaths = [...new Set([...commercePaths, ...publicPaths, "accessibility"])];
export const websiteEntryPaths = ["login", "login/merchant", "login/partner", "login/customer", "login/admin", "partner/login", "merchant"];
export const websiteContactEmail = "ada76145@gmail.com";
export const websiteAliases: Record<string, string> = { "legal/privacy": "privacy", "legal/terms": "terms", trust: "security" };
export const websiteOnly = () => process.env.KUANGUARD_WEBSITE_ONLY === "true";
export const isWebsitePath = (path: string) => websitePaths.includes(path) || websiteEntryPaths.includes(path);
