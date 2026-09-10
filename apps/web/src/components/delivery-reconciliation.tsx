"use client";

import { useState } from "react";
import { dateTime, items, useMutation, useResource, type Row } from "@/lib/api";
import { Card, DataTable, ErrorState, Loading, MutationStatus, Notice, PageHeading, Status } from "./ui";

export function DeliveryReconciliation() {
  const [page, setPage] = useState(1);
  const data = useResource(`/internal/phishing/messages?page=${page}&page_size=20`);
  const [selected, setSelected] = useState<Row | null>(null);
  const [preview, setPreview] = useState<Row | null>(null);
  const [validation, setValidation] = useState("");
  const action = useMutation();
  return <>
    <PageHeading title="供應商接受狀態對帳" description="由財務依供應商證據核對 unknown 訊息，保留核對依據與真實操作者。" />
    <div className="section-stack">
      <Notice tone="warning">此操作不會重新寄送郵件。確認接受後依原預留扣點；確認未接受後釋放預留。供應商接受仍不等於已送達。</Notice>
      <Card title="待對帳訊息" aside={<button className="button button-secondary button-small" disabled={data.loading || action.pending} onClick={data.reload}>重新載入</button>}>
        {data.loading ? <Loading /> : data.error ? <ErrorState error={data.error} retry={data.reload} /> : <DataTable rows={items(data.data)} page={page} total={data.data?.total} onPage={setPage} title="待對帳訊息" columns={[
          { key: "id", title: "訊息識別碼" },
          { key: "campaign_id", title: "活動識別碼" },
          { key: "status", title: "狀態", render: r => <Status value={r.status} /> },
          { key: "provider_ref", title: "現有供應商紀錄" },
          { key: "created_at", title: "建立時間", render: r => dateTime(r.created_at) },
          { key: "reconcile", title: "操作", render: r => <button className="button button-secondary button-small" disabled={action.pending} onClick={() => { setSelected(r); setPreview(null); setValidation(""); action.clear(); }}>核對此訊息</button> },
        ]} />}
      </Card>
      {selected && <Card title="輸入供應商核對證據">
        <form key={selected.id} className="form-stack" onChange={() => { setPreview(null); setValidation(""); action.clear(); }} onSubmit={e => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          const occurred = new Date(String(form.get("occurred_at")));
          if (!Number.isFinite(occurred.getTime()) || occurred.getTime() > Date.now() || occurred.getTime() < new Date(selected.created_at).getTime()) { setValidation("供應商時間必須介於此訊息建立後與現在之間。"); return; }
          setPreview({ outcome: form.get("outcome"), provider_reference: String(form.get("provider_reference")).trim(), occurred_at: occurred.toISOString(), reason: String(form.get("reason")).trim() });
        }}>
          <div className="selection-summary"><strong>訊息：{selected.id}</strong><span>活動：{selected.campaign_id}</span><span>建立時間：{dateTime(selected.created_at)}（Asia/Taipei）</span></div>
          <div className="form-grid">
            <label>已確認的供應商結果<select name="outcome" required defaultValue=""><option value="" disabled>請依證據選擇</option><option value="accepted">供應商確認已接受</option><option value="rejected">供應商確認未接受</option></select></label>
            <label>供應商紀錄編號<input name="provider_reference" required maxLength={120} /></label>
            <label>供應商事件時間（此裝置本地時間）<input type="datetime-local" name="occurred_at" required step={1} /></label>
          </div>
          <label>核對來源與依據（至少 10 字）<textarea name="reason" minLength={10} maxLength={2000} required rows={4} placeholder="填寫已查核的供應商紀錄、時間與判定依據。" /></label>
          {validation && <Notice tone="danger">{validation}</Notice>}
          <div className="actions"><button className="button button-secondary" disabled={action.pending}>預覽對帳結果</button><button className="button button-secondary" type="button" disabled={action.pending} onClick={() => { setSelected(null); setPreview(null); action.clear(); }}>取消</button></div>
        </form>
        {preview && <div className="form-stack section-gap"><div className="selection-summary"><strong>{preview.outcome === "accepted" ? "確認接受，將依原預留扣點" : "確認未接受，將釋放原預留"}</strong><span>供應商紀錄：{preview.provider_reference}</span><span>事件時間：{dateTime(preview.occurred_at)}（Asia/Taipei）</span><span>{preview.reason}</span></div><button className="button" disabled={action.pending} onClick={async () => { if (await action.mutate(`/internal/phishing/messages/${selected.id}/reconcile`, preview)) { setSelected(null); setPreview(null); data.reload(); } }}>確認記錄對帳結果</button></div>}
      </Card>}
      <MutationStatus action={action} success="對帳結果與依據已記錄，沒有重新寄送郵件。" />
      {action.result && <Card title="本次對帳結果"><p>訊息：{action.result.id}</p><p>更新狀態：<Status value={action.result.status} /></p><p>供應商紀錄：{action.result.provider_ref}</p></Card>}
    </div>
  </>;
}
