import type { Locale } from "./locales";
import translations from "./translations.json";

const columns: Record<Exclude<Locale, "zh-TW">, number> = { "zh-CN": 0, en: 1, ja: 2, ko: 3, th: 4, vi: 5 };
const dictionary = translations as Record<string, string[]>;
export function translate(text: string, locale: Locale): string {
  if (locale === "zh-TW") return text;
  const source = text.trim();
  const value = dictionary[source]?.[columns[locale]];
  return value ? text.replace(source, value) : text;
}
