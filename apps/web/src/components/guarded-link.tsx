"use client";

import NextLink from "next/link";
import type { ComponentProps } from "react";
import { confirmFormNavigation, useSession } from "@/lib/api";

export default function GuardedLink({ onNavigate, ...props }: ComponentProps<typeof NextLink>) {
  const { session } = useSession();
  if (session?.delegated && typeof props.href === "string") {
    if (props.href.startsWith("/admin/")) props.href = props.href.replace("/admin/", "/partner/workspace/");
    if (props.href.startsWith("/api/internal/")) props.href = props.href.replace("/api/internal/", "/api/partner/workspace/internal/");
  }
  return <NextLink {...props} onNavigate={event => { if (!confirmFormNavigation()) { event.preventDefault(); return; } onNavigate?.(event); }} />;
}
