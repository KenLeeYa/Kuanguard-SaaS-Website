import type { MetadataRoute } from "next";
import { websitePaths, websiteOnly, websiteAliases } from "@/lib/website";
import { languageAlternates, localePath, locales } from "@/lib/locales";
export default function sitemap(): MetadataRoute.Sitemap {
  const paths = websitePaths.filter(path => !["merchant/apply", "courses"].includes(path) && !websiteAliases[path]);
  if (!websiteOnly()) return paths.map(path => ({ url: `https://kuanguard.com/${path}` }));
  return paths.flatMap(path => locales.map(locale => ({ url: `https://kuanguard.com${localePath(`/${path}`, locale)}`, alternates: { languages: languageAlternates(path) }, changeFrequency: path ? "monthly" as const : "weekly" as const, priority: path ? 0.6 : 1 })));
}
