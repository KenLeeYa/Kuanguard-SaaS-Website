import type { MetadataRoute } from "next";
import { publicPaths } from "@/lib/catalog";
import { commercePaths } from "@/lib/commerce";
export default function sitemap(): MetadataRoute.Sitemap { return [...new Set([...commercePaths, ...publicPaths])].map(path => ({ url: `https://kuanguard.com/${path}`, changeFrequency: path ? "monthly" : "weekly", priority: path ? 0.6 : 1 })); }
