export const locales = ["zh-TW", "zh-CN", "en", "ja", "ko", "th", "vi"] as const;
export type Locale = typeof locales[number];
export const localeNames: Record<Locale, string> = { "zh-TW": "繁體中文", "zh-CN": "简体中文", en: "English", ja: "日本語", ko: "한국어", th: "ไทย", vi: "Tiếng Việt" };
export const openGraphLocales: Record<Locale, string> = { "zh-TW": "zh_TW", "zh-CN": "zh_CN", en: "en_US", ja: "ja_JP", ko: "ko_KR", th: "th_TH", vi: "vi_VN" };
export const localeCookie = "kuanguard-language";
export const isLocale = (value: string): value is Locale => locales.includes(value as Locale);

export function splitLocale(path: string): { locale?: Locale; path: string } {
  const parts = path.replace(/^\/+|\/+$/g, "").split("/");
  const locale = isLocale(parts[0]) ? parts.shift() as Locale : undefined;
  return { locale, path: parts.join("/") };
}

export function preferredLocale(acceptLanguage: string, saved?: string): Locale {
  if (saved && isLocale(saved)) return saved;
  const preferences = acceptLanguage.slice(0, 2048).split(",").map((entry, index) => {
    const [tag, ...parameters] = entry.trim().toLowerCase().split(";");
    const weight = parameters.find(p => p.trim().startsWith("q="));
    return { tag, q: weight ? Number(weight.trim().slice(2)) : 1, index };
  }).filter(p => Number.isFinite(p.q) && p.q > 0 && p.q <= 1).sort((a, b) => b.q - a.q || a.index - b.index);
  for (const { tag } of preferences) {
    if (/^zh(?:-|$)/.test(tag)) return /(?:hans|cn|sg)/.test(tag) && !/hant/.test(tag) ? "zh-CN" : "zh-TW";
    const base = tag.split("-")[0];
    if (isLocale(base)) return base;
  }
  return "zh-TW";
}

export function localePath(href: string, locale: Locale): string {
  if (!href.startsWith("/") || href.startsWith("//")) return href;
  const end = href.search(/[?#]/);
  const pathname = end < 0 ? href : href.slice(0, end);
  const suffix = end < 0 ? "" : href.slice(end);
  const { path } = splitLocale(pathname);
  return `/${locale}${path ? `/${path}` : ""}${suffix}`;
}

export function languageAlternates(path: string) {
  return Object.fromEntries([...locales.map(locale => [locale, `https://kuanguard.com${localePath(`/${path}`, locale)}`]), ["x-default", `https://kuanguard.com/${path}`]]);
}
