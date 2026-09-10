"use client";

import { useState } from "react";
import { EquipmentFields, DispatchNotice } from "./dispatch-page";
import { dateTime, items, useMutation, useResource, useSession, type Row } from "@/lib/api";
import { serviceName, services } from "@/lib/catalog";
import { ButtonLink, Card, DataTable, ErrorState, Loading, MutationStatus, Notice, PageHeading, Status } from "./ui";

export function ProjectControls({ project, reload }: { project: Row; reload: () => void }) {
  const { session } = useSession();
  const grant = useMutation();
  const action = useMutation();
  const [batchId, setBatchId] = useState("");
  const [operation, setOperation] = useState("");
  const pm = !!session?.roles.includes("pm");
  const batch = items(project.batches).find(b => b.id === batchId);
  const choices = batch ? [
    ...(pm && !["delivered", "cancelled"].includes(batch.status) ? [{ value: "cancel", label: "取消未交付批次並釋放預留額度" }] : []),
    ...(pm && ["approved", "delivered"].includes(batch.status) ? [{ value: "reopen", label: "提出更正，保留原發布版本" }] : []),
    ...(session?.roles.includes("engineer") && batch.engineer_id === session.user.id && ["preparing", "confirmed"].includes(batch.status) ? [{ value: "submit-review", label: "使用已提交來源重新送審" }] : []),
  ] : [];
  return <div className="section-stack">
    {pm && <Card title="核定服務額度">
      <Notice>服務次數與企業點數分開。新增批次前需有足夠額度；本次核定上限為 100 個服務單位，並留下核定依據。</Notice>
      {Array.isArray(project.entitlements) && <DataTable rows={project.entitlements} title="專案服務額度" columns={[{ key: "service_code", title: "服務", render: r => serviceName(r.service_code) }, { key: "quantity", title: "原核定" }, { key: "available", title: "可用" }, { key: "reserved", title: "已預留" }, { key: "consumed", title: "已履約耗用" }]} />}
      <form className="form-stack section-gap" onChange={grant.clear} onSubmit={async e => {
        e.preventDefault(); const form = new FormData(e.currentTarget);
        await grant.mutate("/internal/entitlements/grants", { project_id: project.id, service_code: form.get("service_code"), quantity: Number(form.get("quantity")), reason: String(form.get("reason")).trim() });
      }}>
        <div className="form-grid"><label>服務<select name="service_code" required>{services.map(s => <option key={s.code} value={s.code}>{s.name}</option>)}</select></label><label>核定服務單位數<input name="quantity" type="number" min={1} max={100} step={1} required /></label></div>
        <label>合約／核定依據（至少 10 字）<textarea name="reason" minLength={10} maxLength={1000} required rows={3} /></label>
        <label className="answer-option"><input type="checkbox" required />我已確認本專案的合約範圍及授權數量。</label>
        <button className="button" disabled={grant.pending || !!grant.result}>核定並記錄服務額度</button><MutationStatus action={grant} success="服務額度已核定，與點數錢包分開記帳。" />
        {grant.result && <><Notice tone="success">{serviceName(grant.result.service_code)}：本次額度批次可用 {grant.result.available}，已預留 {grant.result.reserved}，已耗用 {grant.result.consumed}。</Notice><button className="button button-secondary" type="button" onClick={reload}>重新載入專案額度與批次</button></>}
      </form>
    </Card>}
    <Card title="批次更正、取消與重新送審"><form className="form-stack" onChange={action.clear} onSubmit={async e => {
      e.preventDefault(); const form = new FormData(e.currentTarget);
      if (await action.mutate(`/internal/batches/${batchId}/${operation}`, { text: String(form.get("reason")).trim() })) reload();
    }}>
      <label>授權批次<select value={batchId} onChange={e => { setBatchId(e.target.value); setOperation(""); }} required><option value="">選擇批次</option>{items(project.batches).map(b => <option key={b.id} value={b.id}>{b.title} · {b.status}</option>)}</select></label>
      <label>操作<select value={operation} onChange={e => setOperation(e.target.value)} required><option value="">選擇可執行操作</option>{choices.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}</select></label>
      {batch && !choices.length && <Notice>此批次目前沒有可由您的角色執行的取消、更正或重送操作。</Notice>}
      <label>操作原因<textarea name="reason" required maxLength={10000} rows={3} /></label>
      <Notice>{operation === "cancel" ? "取消將釋放尚未交付批次的原額度預留及排程，已發布版本不能藉此撤銷。" : operation === "reopen" ? "更正會建立新批次版本、清除目前覆核核定，原發布版本與下載歷史保留，需重新送審與發布。" : "重新送審使用已有的 committed 來源資料；仍需通過目前指派與專案覆核政策。"}</Notice>
      <label className="answer-option"><input type="checkbox" key={`${batchId}:${operation}`} required />我已確認所選批次、操作內容及原因。</label>
      <button className="button" disabled={action.pending || !batch || !operation}>確認記錄批次操作</button><MutationStatus action={action} />
    </form></Card>
    {pm && <Card title="客戶範圍與改期申請"><p>報價版本由客戶明確確認後，PM 才能套用範圍或重新派工；已執行範圍需建立追加批次。</p><ButtonLink href="/admin/changes">處理變更申請</ButtonLink></Card>}
  </div>;
}

export function ChangeSummary({ change }: { change: Row }) {
  return <div className="selection-summary"><strong>{change.kind === "scope" ? "範圍追加" : "改期申請"} · v{change.version}</strong><span>批次：{change.batch_id}</span><span>{change.reason}</span>{change.kind === "scope" ? <span className="preserve-lines">提出追加範圍：{(change.proposed_assets || []).join("\n")}</span> : <span>提出開始時間：{dateTime(change.proposed_start)}（Asia/Taipei）</span>}<span>前版變更費用：{change.old_amount_minor == null ? "尚無前版" : `TWD ${(change.old_amount_minor / 100).toLocaleString()}`}</span><span>本版變更費用：{change.new_amount_minor == null ? "尚未報價" : `TWD ${(change.new_amount_minor / 100).toLocaleString()}`}</span></div>;
}

export function InternalChanges() {
  const [page, setPage] = useState(1);
  const data = useResource(`/internal/changes?page=${page}&page_size=20`);
  const people = useResource("/internal/dispatch");
  const [selected, setSelected] = useState<Row | null>(null);
  const action = useMutation();
  return <>
    <PageHeading title="範圍與時程變更" description="核對客戶需求、提出費用版本，客戶確認後才套用；每個版本保留原範圍與操作依據。" />
    <div className="section-stack">
      <Card title="授權專案的變更申請">{data.loading ? <Loading /> : data.error ? <ErrorState error={data.error} retry={data.reload} /> : <DataTable rows={items(data.data)} page={page} total={data.data?.total} onPage={setPage} title="變更申請" columns={[
        { key: "project_id", title: "專案" }, { key: "batch_id", title: "批次" }, { key: "kind", title: "類型", render: r => r.kind === "scope" ? "範圍追加" : "改期" }, { key: "status", title: "狀態", render: r => <Status value={r.status} /> }, { key: "version", title: "版本" }, { key: "action", title: "操作", render: r => <button className="button button-secondary button-small" disabled={action.pending} onClick={() => { setSelected(r); action.clear(); }}>檢視與處理</button> },
      ]} />}</Card>
      {selected && <Card title="變更內容"><div className="form-stack"><ChangeSummary change={selected} /><p>目前狀態：<Status value={selected.status} /></p>
        {["requested", "offered"].includes(selected.status) && <form key={`${selected.id}:${selected.version}`} className="form-stack" onChange={action.clear} onSubmit={async e => {
          e.preventDefault(); const form = new FormData(e.currentTarget);
          const result = await action.mutate(`/internal/changes/${selected.id}/offer`, { expected_version: selected.version, amount_minor: Math.round(Number(form.get("amount")) * 100), reason: String(form.get("reason")).trim() });
          if (result) { setSelected(result); data.reload(); }
        }}><label>本版變更費用（新台幣元）<input name="amount" type="number" min={0} max={20000000} step={0.01} required /></label><label>費用與範圍核定依據（至少 10 字）<textarea name="reason" minLength={10} maxLength={1000} required rows={3} /></label><Notice>提出報價會新增版本，需客戶另行確認；零元變更也必須保留原因。</Notice><button className="button" disabled={action.pending}>確認提出變更費用版本</button></form>}
        {selected.status === "confirmed" && <form key={`${selected.id}:${selected.version}:apply`} className="form-stack" onSubmit={async e => {
          e.preventDefault(); const form = new FormData(e.currentTarget);
          const result = await action.mutate(`/internal/changes/${selected.id}/apply`, { expected_version: selected.version, ...(selected.kind === "reschedule" ? { schedule: { start_at: selected.proposed_start, end_at: new Date(String(form.get("end_at"))).toISOString(), engineer_id: form.get("engineer_id"), reviewer_id: form.get("reviewer_id"), equipment: form.get("equipment"), equipment_units: Number(form.get("equipment_units")), reason: String(form.get("reason")).trim() } } : {}) });
          if (result) { setSelected(result); data.reload(); }
        }}>
          {selected.kind === "reschedule" && <>{people.error ? <ErrorState error={people.error} retry={people.reload} /> : <><div className="form-grid"><label>結束時間（裝置本地時間）<input name="end_at" type="datetime-local" required /></label><label>工程師<select name="engineer_id" required><option value="">選擇工程師</option>{items(people.data).filter(p => p.roles?.includes("engineer")).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label>覆核者<select name="reviewer_id" required><option value="">選擇覆核者</option>{items(people.data).filter(p => p.roles?.includes("reviewer")).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><EquipmentFields data={people.data} /></div><DispatchNotice data={people.data} /><label>排程核對原因<textarea name="reason" required maxLength={1000} rows={3} /></label></>}</>}
          <Notice>只可套用尚未執行或匯入的批次。改期使用客戶確認的開始時間，並重新檢查工程師、覆核者、設備與時段衝突。</Notice>
          <label className="answer-option"><input type="checkbox" required />我已核對此版本的客戶確認、範圍、費用與派工。</label><button className="button" disabled={action.pending || (selected.kind === "reschedule" && (!!people.error || people.loading))}>確認套用已核定變更</button>
        </form>}
        <MutationStatus action={action} success="變更操作已記錄；列表顯示後端確認狀態。" />
      </div></Card>}
    </div>
  </>;
}

export function CustomerChangeOffers({ changes, reload }: { changes: Row[]; reload: () => void }) {
  const [selected, setSelected] = useState<Row | null>(null);
  const action = useMutation();
  return <Card title="待確認的變更報價"><div className="form-stack">
    <DataTable rows={changes.filter(c => c.status === "offered")} title="待確認變更" columns={[{ key: "kind", title: "類型", render: r => r.kind === "scope" ? "範圍追加" : "改期" }, { key: "version", title: "版本" }, { key: "new_amount_minor", title: "本版費用（TWD）", render: r => r.new_amount_minor == null ? "尚未報價" : (r.new_amount_minor / 100).toLocaleString() }, { key: "confirm", title: "操作", render: r => <button className="button button-secondary button-small" disabled={action.pending} onClick={() => { setSelected(r); action.clear(); }}>檢視費用與範圍</button> }]} />
    {selected && <form key={`${selected.id}:${selected.version}`} className="form-stack" onSubmit={async e => { e.preventDefault(); if (await action.mutate(`/customer/changes/${selected.id}/confirm`, { version: selected.version, intent: "accept" })) { setSelected(null); reload(); } }}>
      <ChangeSummary change={selected} /><Notice>確認僅代表接受本版變更範圍與費用；正式時程仍需專案團隊檢查派工衝突後套用，不會立即扣取真實款項。</Notice>
      <label className="answer-option"><input type="checkbox" required />我已閱讀本版範圍、日期與費用，明確接受此變更內容。</label><div className="actions"><button className="button" disabled={action.pending}>確認接受此版本</button><button className="button button-secondary" type="button" disabled={action.pending} onClick={() => { setSelected(null); action.clear(); }}>返回檢視</button></div>
    </form>}
    <MutationStatus action={action} success="此版本已由您確認，等待 PM 套用。" />
  </div></Card>;
}
