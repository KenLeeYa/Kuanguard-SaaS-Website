"use client";

import type { ReactNode } from "react";
import { dateTime } from "@/lib/api";
import type { DraftPayload } from "@/lib/draft-store";
import type { useServerDraft } from "@/lib/use-server-draft";
import { Notice } from "./ui";

export function DraftStatus<T extends DraftPayload>({ draft, describe }: { draft: ReturnType<typeof useServerDraft<T>>; describe: (payload: T) => ReactNode }) {
  if (draft.loading) return <Notice>正在確認目前企業與操作者的伺服器草稿…</Notice>;
  if (draft.conflict) return <div className="form-stack draft-conflict" role="alert">
    <Notice tone="warning">另一個視窗已更新或清除草稿。自動儲存已停止，此頁輸入仍保留，沒有覆寫伺服器內容。</Notice>
    <div className="two-col"><div className="selection-summary"><strong>此頁尚未儲存內容</strong>{describe(draft.payload)}</div><div className="selection-summary"><strong>伺服器目前版本 {draft.remote?.version || "待重新確認"}</strong>{draft.remote ? describe(draft.remote.payload) : <span>目前無法取得有效版本，請重新確認。</span>}</div></div>
    <p className="form-help">載入新版會捨棄此頁未儲存變更。若要保留，請先記下需要的欄位，再載入與重新編輯。</p>
    <button type="button" className="button button-secondary" onClick={() => { if (window.confirm("載入伺服器新版將取代此頁尚未儲存的內容，確定載入？")) void draft.loadLatest(); }}>載入伺服器新版</button>
  </div>;
  return <div className="form-stack draft-status" aria-live="polite">
    <Notice tone={draft.error ? "warning" : "info"}>{draft.error ? `草稿目前未儲存：${draft.error.message}` : draft.saving ? "正在儲存草稿…" : draft.dirty ? "有變更等待自動儲存。" : draft.record ? `${draft.restored ? "已恢復" : "已儲存"}伺服器草稿 v${draft.record.version}。` : "填寫後自動儲存至目前企業與操作者的草稿。"}{draft.record && <small>儲存：{dateTime(draft.record.updated_at)} · 到期：{dateTime(draft.record.expires_at)}（Asia/Taipei）</small>}</Notice>
    <div className="actions">{(draft.dirty || draft.error) && <button type="button" className="button button-secondary button-small" disabled={draft.saving} onClick={() => { if (!draft.initialized) void draft.loadLatest(); else void draft.saveNow(); }}>重試／立即儲存草稿</button>}{(draft.record || draft.dirty) && <button type="button" className="button button-secondary button-small" disabled={draft.saving} onClick={() => { if (window.confirm("刪除目前版本的伺服器草稿並清除此頁輸入？")) void draft.clear(); }}>刪除此份草稿</button>}</div>
    <p className="form-help">草稿保存 24 小時；只保存此流程的設定欄位，不保存名單、密碼或原始檢測證據，也不存入瀏覽器儲存空間。</p>
  </div>;
}
