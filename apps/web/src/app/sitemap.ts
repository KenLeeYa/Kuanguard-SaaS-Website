import type { MetadataRoute } from "next";
import { publicPaths } from "@/lib/catalog";
export default function sitemap(): MetadataRoute.Sitemap { return publicPaths.map(path => ({ url: `https://kuanguard.com/${path}`, changeFrequency: path ? "monthly" : "weekly", priority: path ? 0.6 : 1 })); }
