"use client";

import { Children, cloneElement, createContext, isValidElement, useContext, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { ChevronDown, Globe2 } from "lucide-react";
import { isLocale, localeCookie, localeNames, localePath, locales, type Locale } from "@/lib/locales";
import { translate } from "@/lib/translate";

const LanguageContext = createContext<Locale | null>(null);
export function WebsiteLanguage({ locale, children }: { locale: Locale; children: ReactNode }) {
  return <LanguageContext.Provider value={locale}>{children}</LanguageContext.Provider>;
}
export const useWebsiteLocale = () => useContext(LanguageContext);
export function useWebsiteText() { const locale = useWebsiteLocale(); return (text: string) => translate(text, locale || "zh-TW"); }

// Translate presentation text at render time, including server rendering. Identifiers,
// form values, URLs and event handlers are left intact.
export function Localized({ children }: { children: ReactNode }) {
  const locale = useWebsiteLocale();
  if (!locale || locale === "zh-TW") return children;
  function visit(nodes: ReactNode): ReactNode {
    return Children.map(nodes, node => {
      if (typeof node === "string") return translate(node, locale!);
      if (!isValidElement<Record<string, unknown>>(node)) return node;
      const props: Record<string, unknown> = {};
      for (const key of ["title", "description", "eyebrow", "aria-label", "placeholder", "alt"]) {
        if (typeof node.props[key] === "string") props[key] = translate(node.props[key], locale!);
      }
      if (node.props.children !== undefined) props.children = visit(node.props.children as ReactNode);
      return cloneElement(node, props);
    });
  }
  return visit(children);
}

export function LanguageSwitcher() {
  const locale = useWebsiteLocale();
  const path = usePathname();
  const text = useWebsiteText();
  if (!locale) return null;
  return <span className="kg-language"><Globe2 className="kg-language-globe" size={18} aria-hidden="true" /><select aria-label={text("網站語言")} lang={locale} value={locale} onChange={event => {
    const next = event.target.value;
    if (!isLocale(next)) return;
    document.cookie = `${localeCookie}=${next}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
    window.location.assign(localePath(path, next) + location.search + location.hash);
  }}>{locales.map(value => <option key={value} value={value} lang={value}>{localeNames[value]}</option>)}</select><ChevronDown className="kg-language-chevron" size={16} aria-hidden="true" /></span>;
}
