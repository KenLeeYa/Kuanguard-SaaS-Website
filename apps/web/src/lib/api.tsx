"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

export type Row = Record<string, any>;
export type Session = { user: { id: string; name: string }; tenant: { id: string; name: string }; roles: string[]; csrf_token: string; development: boolean; partner_id?: string; partner_branding?: Row; delegated?: boolean; platform_admin?: boolean; features?: Record<string, boolean> };
let delegatedWorkspace = false;
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public trace?: string) { super(message); }
}
export async function request<T = Row>(path: string, options: { method?: string; body?: unknown; csrf?: string; key?: string; signal?: AbortSignal } = {}): Promise<T> {
  if (delegatedWorkspace && path.startsWith("/internal/")) path = "/partner/workspace" + path;
  const response = await fetch(`/api${path}`, { method: options.method || "GET", credentials: "same-origin", cache: "no-store", signal: options.signal, headers: {
    ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
    ...(options.csrf ? { "X-CSRF-Token": options.csrf } : {}),
    ...(options.key ? { "Idempotency-Key": options.key } : {}),
  }, body: options.body === undefined ? undefined : JSON.stringify(options.body) });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail;
    throw new ApiError(response.status, detail?.code || "REQUEST_FAILED", typeof detail === "string" ? detail : Array.isArray(detail) ? "欄位內容不符合要求，請檢查格式、長度與必填欄位。" : detail?.message || "目前無法完成，請稍後再試。", detail?.trace_id);
  }
  return payload as T;
}
const SessionContext = createContext<{ session: Session | null; loading: boolean; error: Error | null; refresh: () => Promise<void> }>({ session: null, loading: true, error: null, refresh: async () => {} });
export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try { const current = await request<Session>("/auth/me"); delegatedWorkspace = !!current.delegated; setSession(current); }
    catch (e) { delegatedWorkspace = false; setSession(null); if (!(e instanceof ApiError && e.status === 401)) setError(e as Error); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  return <SessionContext.Provider value={{ session, loading, error, refresh }}>{children}</SessionContext.Provider>;
}
export const useSession = () => useContext(SessionContext);
export function useResource<T = Row>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(!!path);
  const [error, setError] = useState<Error | null>(null);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    setData(null); setError(null);
    if (!path) { setLoading(false); return; }
    const controller = new AbortController(); setLoading(true);
    request<T>(path, { signal: controller.signal }).then(setData).catch(e => { if (e.name !== "AbortError") setError(e); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [path, version]);
  return { data, loading, error, reload: () => setVersion(v => v + 1) };
}
export function useMutation() {
  const { session } = useSession();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [result, setResult] = useState<Row | null>(null);
  const retry = useRef<{ signature: string; key: string } | null>(null);
  const inFlight = useRef(false);
  async function mutate(path: string, body: unknown = {}, method = "POST") {
    if (inFlight.current) return null;
    inFlight.current = true; setPending(true); setError(null); setResult(null);
    const signature = `${method}:${path}:${JSON.stringify(body)}`;
    if (retry.current?.signature !== signature) retry.current = { signature, key: crypto.randomUUID() };
    try {
      const value = await request(path, { method, body, csrf: session?.csrf_token, key: retry.current.key });
      setResult(value); retry.current = null; return value;
    } catch (e) { setError(e as Error); return null; }
    finally { inFlight.current = false; setPending(false); }
  }
  return { mutate, pending, error, result, clear: () => { setError(null); setResult(null); } };
}
export const items = (data: any): Row[] => Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];
export const dateTime = (value: unknown) => value && Number.isFinite(new Date(String(value)).getTime()) ? new Intl.DateTimeFormat("zh-TW", { timeZone: "Asia/Taipei", dateStyle: "medium", timeStyle: "short", hour12: false }).format(new Date(String(value))) : "尚未安排";
export const dateOnly = (value: unknown) => value && Number.isFinite(new Date(String(value)).getTime()) ? new Intl.DateTimeFormat("zh-TW", { timeZone: "Asia/Taipei", dateStyle: "medium" }).format(new Date(String(value))) : "—";
const dirtyForms = new Set<symbol>();
export function confirmFormNavigation() { return dirtyForms.size === 0 || window.confirm("目前有尚未儲存或發生衝突的輸入，離開後可能遺失此頁變更。確定離開？"); }
export function useDirtyForm(dirty: boolean) {
  const identity = useRef(Symbol("dirty-form"));
  useEffect(() => {
    const token = identity.current;
    const handler = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    if (dirty) { dirtyForms.add(token); window.addEventListener("beforeunload", handler); }
    return () => { dirtyForms.delete(token); window.removeEventListener("beforeunload", handler); };
  }, [dirty]);
}
