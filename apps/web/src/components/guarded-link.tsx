"use client";

import NextLink from "next/link";
import type { ComponentProps } from "react";
import { confirmFormNavigation, useSession } from "@/lib/api";
import { useWebsiteLocale } from "./website-language";
import { localePath, splitLocale } from "@/lib/locales";
import { publicDestination } from "@/lib/product-links";

export default function GuardedLink({ onNavigate, ...props }: ComponentProps<typeof NextLink>) {
  const { session } = useSession();
  const locale = useWebsiteLocale();
  if (locale && typeof props.href === "string" && props.href.startsWith("/") && !props.href.startsWith("//")) {
    const path = splitLocale(props.href.split(/[?#]/)[0]).path;
    props.href = publicDestination(path) || localePath(props.href, locale);
  }
  if (session?.delegated && typeof props.href === "string") {
    if (props.href.startsWith("/admin/")) props.href = props.href.replace("/admin/", "/partner/workspace/");
    if (props.href.startsWith("/api/internal/")) props.href = props.href.replace("/api/internal/", "/api/partner/workspace/internal/");
  }
  return <NextLink {...props} onNavigate={event => { if (!confirmFormNavigation()) { event.preventDefault(); return; } onNavigate?.(event); }} />;
}
