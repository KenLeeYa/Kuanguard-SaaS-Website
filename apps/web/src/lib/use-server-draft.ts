"use client";

import { useEffect, useMemo, useSyncExternalStore } from "react";
import { request, useDirtyForm, useSession } from "./api";
import { DraftStore, type DraftPayload, type DraftRecord } from "./draft-store";

export function useServerDraft<T extends DraftPayload>(kind: "campaign" | "training" | "purchase", initial: T) {
  const { session } = useSession();
  const tenant = session?.tenant.id;
  const actor = session?.user.id;
  const csrf = session?.csrf_token;
  const store = useMemo(() => {
    const path = `/app/drafts/${kind}/new`;
    return new DraftStore(initial, {
      get: () => request<DraftRecord<T>>(path),
      put: (expected_version, payload, key) => request<DraftRecord<T>>(path, { method: "PUT", csrf, key, body: { expected_version, payload } }),
      remove: (version, key) => request(`${path}?version=${version}`, { method: "DELETE", csrf, key }),
    });
  }, [tenant, actor, csrf, kind]);
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  useEffect(() => { if (session) void store.load(); }, [store, !!session]);
  useEffect(() => {
    if (!state.initialized || state.loading || state.saving || state.conflict || state.error || !store.dirty) return;
    const timer = window.setTimeout(() => { void store.save(); }, 800);
    return () => window.clearTimeout(timer);
  }, [state, store]);
  useDirtyForm(store.dirty || state.saving || state.conflict);
  return { ...state, dirty: store.dirty, edit: store.edit, saveNow: store.save, clear: store.clear, loadLatest: store.load, ready: state.initialized && !state.loading && !state.conflict && !state.error };
}

export function localDateTime(iso: string | null) {
  if (!iso) return "";
  const value = new Date(iso);
  if (!Number.isFinite(value.getTime())) return "";
  const pad = (number: number) => String(number).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`;
}
