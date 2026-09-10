"use client";

import NextLink from "next/link";
import type { ComponentProps } from "react";
import { confirmFormNavigation } from "@/lib/api";

export default function GuardedLink({ onNavigate, ...props }: ComponentProps<typeof NextLink>) {
  return <NextLink {...props} onNavigate={event => { if (!confirmFormNavigation()) { event.preventDefault(); return; } onNavigate?.(event); }} />;
}
