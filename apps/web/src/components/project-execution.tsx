"use client";

import { useState } from "react";
import { ApiError, confirmFormNavigation, dateTime, items, useDirtyForm, useMutation, useResource, useSession, type Row } from "@/lib/api";
import { localDateTime } from "@/lib/use-server-draft";
import { Card, DataTable, ErrorState, Loading, MutationStatus, Notice, PageHeading, Status } from "./ui";

const taskStatuses = { open: "待處理", in_progress: "進行中", blocked: "受阻", done: "完成" };
const visibilityLabel = (value: string) => value === "customer" ? "客戶可見" : "僅內部";
const optional = (form: FormData, name: string) => String(form.get(name) || "").trim() || null;
function ReferenceOptions({ rows, selected = [] }: { rows: Row[]; selected?: string[] }) {
  return <>{rows.map(row => <option value={row.id} key={row.id}>{row.title || row.name || row.id}</option>)}{selected.filter(id => !rows.some(row => row.id === id)).map(id => <option key={id} value={id}>既有關聯 · {id}</option>)}</>;
}

export function ProjectTasks({ project, internal = false }: { project: Row; internal?: boolean }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Row | null>(null);
  const [dirty, setDirty] = useState(false);
  const { session } = useSession();
  const editable = internal && !!session?.roles.includes("pm");
  const path = `/${internal ? "internal" : "customer"}/projects/${project.id}/tasks`;
  const data = useResource(`${path}?page=${page}&page_size=20`);
  const people = useResource(editable ? "/internal/dispatch" : null);
  const action = useMutation();
  useDirtyForm(dirty);
  function choose(row: Row) { if (!confirmFormNavigation()) return; setSelected(row); setDirty(false); action.clear(); }
  return <div className="section-stack"><Card title="專案待辦與依賴" aside={editable && <button className="button button-small" onClick={() => choose({})}>新增待辦</button>}>
    <p className="form-help">{internal ? "內部備註及指派人員只供內部使用。" : "僅顯示此專案已公開給客戶的待辦與關聯。"}前置待辦未完成時，實際狀態會顯示受阻。</p>
    {data.loading ? <Loading /> : data.error ? <ErrorState error={data.error} retry={data.reload} /> : <DataTable rows={items(data.data)} title="專案待辦" page={page} total={data.data?.total} onPage={setPage} columns={[
      { key: "title", title: "待辦", render: row => <><strong>{row.title}</strong><small>v{row.version} · {visibilityLabel(row.visibility)}</small></> }, { key: "effective_status", title: "目前狀態", render: row => <Status value={row.effective_status} /> }, { key: "due_at", title: "期限", render: row => dateTime(row.due_at) }, { key: "customer_note", title: "專案說明", render: row => <p className="preserve-lines">{row.customer_note || "尚無說明"}</p> }, { key: "dependency_ids", title: "前置待辦", render: row => (row.dependency_ids || []).map((id: string) => items(data.data).find(task => task.id === id)?.title || id).join("、") || "無" },
      ...(internal ? [{ key: "internal_note", title: "內部備註", render: (row: Row) => <p className="preserve-lines">{row.internal_note || "—"}</p> }] : []), ...(editable ? [{ key: "edit", title: "管理", render: (row: Row) => <button className="button button-secondary button-small" onClick={() => choose(row)}>編輯 v{row.version}</button> }] : []),
    ]} />}
  </Card>
    {selected && editable && <Card title={selected.id ? "更新待辦版本" : "建立專案待辦"}><form key={`${selected.id || "new"}:${selected.version || 0}`} className="form-stack" onChange={() => setDirty(true)} onSubmit={async event => {
      event.preventDefault(); const form = new FormData(event.currentTarget); const due = optional(form, "due_at");
      const result = await action.mutate(selected.id ? `/internal/tasks/${selected.id}` : path, { title: String(form.get("title")).trim(), status: form.get("status"), visibility: form.get("visibility"), customer_note: String(form.get("customer_note")), internal_note: String(form.get("internal_note")), batch_id: optional(form, "batch_id"), assigned_to: optional(form, "assigned_to"), due_at: due ? new Date(due).toISOString() : null, dependency_ids: form.getAll("dependency_ids"), ...(selected.id ? { expected_version: selected.version } : {}) });
      if (result) { setSelected(result); setDirty(false); data.reload(); }
    }}>
      <label>待辦標題<input name="title" required maxLength={120} defaultValue={selected.title || ""} /></label><div className="form-grid"><label>狀態<select name="status" defaultValue={selected.status || "open"}>{Object.entries(taskStatuses).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label><label>可見範圍<select name="visibility" defaultValue={selected.visibility || "internal"}><option value="internal">僅內部</option><option value="customer">客戶可見</option></select></label><label>期限（裝置本地時間，可空白）<input name="due_at" type="datetime-local" defaultValue={localDateTime(selected.due_at)} /></label><label>關聯批次<select name="batch_id" defaultValue={selected.batch_id || ""}><option value="">不關聯</option><ReferenceOptions rows={items(project.batches)} selected={selected.batch_id ? [selected.batch_id] : []} /></select></label><label>指派人員<select name="assigned_to" defaultValue={selected.assigned_to || ""}><option value="">尚未指派</option><ReferenceOptions rows={items(people.data)} selected={selected.assigned_to ? [selected.assigned_to] : []} /></select></label></div>
      <label>客戶說明<textarea name="customer_note" maxLength={10000} rows={3} defaultValue={selected.customer_note || ""} /></label><label>內部備註<textarea name="internal_note" maxLength={10000} rows={3} defaultValue={selected.internal_note || ""} /></label><label>前置待辦（可多選，最多 20 項）<select name="dependency_ids" multiple defaultValue={selected.dependency_ids || []} size={5}><ReferenceOptions rows={items(data.data).filter(row => row.id !== selected.id)} selected={selected.dependency_ids || []} /></select></label><p className="form-help">顯示目前頁面的待辦及原有關聯；指派與依賴仍由後端核對專案授權。手動設為受阻時，請填寫原因說明。</p>
      <button className="button" disabled={action.pending}>{selected.id ? `儲存自 v${selected.version} 的更新` : "確認新增待辦"}</button>
      {action.error instanceof ApiError && action.error.status === 409 && <Notice tone="warning">更新未套用，輸入仍保留。請重新讀取列表並比較，再選取最新版本。<button type="button" className="button button-secondary section-gap" onClick={data.reload}>重新讀取待辦</button></Notice>}
      <MutationStatus action={action} success="待辦已儲存，版本與前置條件已重新核對。" />
    </form></Card>}
  </div>;
}

export function ProjectDecisions({ project, internal = false }: { project: Row; internal?: boolean }) {
  const [page, setPage] = useState(1); const [dirty, setDirty] = useState(false); const [visibility, setVisibility] = useState("internal");
  const { session } = useSession(); const editable = internal && !!session?.roles.includes("pm");
  const path = `/${internal ? "internal" : "customer"}/projects/${project.id}/decisions`;
  const data = useResource(`${path}?page=${page}&page_size=20`);
  const tasks = useResource(editable ? `/internal/projects/${project.id}/tasks?page_size=100` : null);
  const action = useMutation(); useDirtyForm(dirty);
  return <div className="section-stack"><Card title="會議決議與紀錄"><Notice>決議以新增方式留存，更正請另建一則。{internal ? "客戶只會看到標示為客戶可見的對外說明與已授權關聯。" : "此頁為已提供給客戶的決議紀錄。"}</Notice>
    {data.loading ? <Loading /> : data.error ? <ErrorState error={data.error} retry={data.reload} /> : <DataTable rows={items(data.data)} title="專案決議" page={page} total={data.data?.total} onPage={setPage} columns={[{ key: "title", title: "決議", render: row => <><strong>{row.title}</strong><small>{visibilityLabel(row.visibility)}</small></> }, { key: "occurred_at", title: "會議時間", render: row => dateTime(row.occurred_at) }, { key: "customer_text", title: "對外決議", render: row => <p className="preserve-lines">{row.customer_text || "—"}</p> }, { key: "scope_version", title: "範圍版本", render: row => row.scope_version ? `v${row.scope_version}` : "未關聯批次" }, { key: "publication_id", title: "正式報告版本" }, ...(internal ? [{ key: "internal_note", title: "內部備註", render: (row: Row) => <p className="preserve-lines">{row.internal_note || "—"}</p> }] : [])]} />}
  </Card>{editable && <Card title="新增決議"><form className="form-stack" onChange={() => { setDirty(true); action.clear(); }} onSubmit={async event => { event.preventDefault(); const form = new FormData(event.currentTarget); const result = await action.mutate(path, { title: String(form.get("title")).trim(), occurred_at: new Date(String(form.get("occurred_at"))).toISOString(), visibility, customer_text: String(form.get("customer_text")), internal_note: String(form.get("internal_note")), batch_id: optional(form, "batch_id"), publication_id: optional(form, "publication_id"), task_ids: form.getAll("task_ids") }); if (result) { setDirty(false); data.reload(); } }}>
    <div className="form-grid"><label>決議標題<input name="title" required maxLength={120} /></label><label>會議時間（裝置本地時間）<input name="occurred_at" type="datetime-local" required /></label><label>可見範圍<select value={visibility} onChange={event => setVisibility(event.target.value)}><option value="internal">僅內部</option><option value="customer">客戶可見</option></select></label><label>關聯批次<select name="batch_id"><option value="">不關聯</option><ReferenceOptions rows={items(project.batches)} /></select></label><label>已發布報告<select name="publication_id"><option value="">不關聯</option><ReferenceOptions rows={items(project.reports)} /></select></label></div>
    <label>對外決議文字<textarea name="customer_text" required={visibility === "customer"} maxLength={10000} rows={4} /></label><label>內部備註<textarea name="internal_note" required={visibility === "internal"} maxLength={10000} rows={3} /></label><label>關聯待辦（本次最多顯示 100 項，可多選最多 20 項）<select name="task_ids" multiple size={5}><ReferenceOptions rows={items(tasks.data)} /></select></label><label className="answer-option"><input type="checkbox" required />已確認可見範圍、決議內容及所關聯的正式版本。</label><button className="button" disabled={action.pending || !!action.result}>確認新增決議紀錄</button><MutationStatus action={action} success="決議已新增，原有會議紀錄保持完整。" />
  </form></Card>}</div>;
}

const costCategories = { onsite: "現場作業", travel: "交通", analysis: "分析", review: "覆核", retest: "複測", tools: "工具", cloud: "雲端", outsource: "委外", other: "其他" };
const marginReasons: Record<string, string> = { no_active_contract: "尚未關聯有效合約", cost_not_entered: "尚未登錄成本", unpriced_entries: "仍有待定價成本", mixed_cost_currencies: "成本包含不同幣別", contract_quote_amount_mismatch: "合約與報價金額不一致", legacy_costs_unclassified: "舊成本尚未分類", cost_currency_mismatch: "成本與合約幣別不一致" };
export function ProjectCosts({ projectId }: { projectId: string }) {
  const [page, setPage] = useState(1); const [priced, setPriced] = useState(false); const [dirty, setDirty] = useState(false); const [selected, setSelected] = useState<Row | null>(null);
  const path = `/internal/projects/${projectId}/costs`; const data = useResource(`${path}?page=${page}&page_size=20`); const action = useMutation(); const voidAction = useMutation(); useDirtyForm(dirty);
  return <div className="section-stack"><Card title="預估與實際工時／成本"><Notice>未定價以「待定價」顯示。金額是本筆總成本；不同幣別分列。毛利僅為有效合約金額減已登錄成本，不代表正式收入認列。</Notice>
    {data.loading ? <Loading /> : data.error ? <ErrorState error={data.error} retry={data.reload} /> : <><div className="two-col section-gap">{["estimated", "actual"].map(phase => { const total = data.data?.totals?.[phase]; return <div className="selection-summary" key={phase}><strong>{phase === "estimated" ? "預估" : "實際"}</strong><span>工時：{total?.minutes ?? "尚無資料"} 分鐘</span><span>未定價：{total?.unpriced_entries ?? "尚無資料"} 筆</span>{items(total?.amounts).map(amount => <span key={amount.currency}>{amount.currency} {(amount.cost_minor / 100).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>)}{!items(total?.amounts).length && <span>尚無已定價成本</span>}</div>; })}</div>
      <DataTable rows={items(data.data)} title="專案成本" page={page} total={data.data?.total} onPage={setPage} columns={[{ key: "phase", title: "階段", render: row => row.phase === "estimated" ? "預估" : "實際" }, { key: "category", title: "分類", render: row => costCategories[row.category as keyof typeof costCategories] || row.category }, { key: "minutes", title: "工時（分）" }, { key: "cost_minor", title: "本筆總金額", render: row => row.cost_minor == null ? "待定價" : `${row.currency} ${(row.cost_minor / 100).toLocaleString(undefined, { minimumFractionDigits: 2 })}` }, { key: "note", title: "說明", render: row => <p>{row.note}</p> }, { key: "voided_at", title: "狀態", render: row => row.voided_at ? <span>已作廢 · {row.void_reason}</span> : <button className="button button-secondary button-small" onClick={() => { setSelected(row); voidAction.clear(); }}>更正／作廢</button> }]} />
      {items(data.data?.legacy_entries).length > 0 && <Notice>另有 {items(data.data?.legacy_entries).length} 筆舊工時缺少階段或幣別，保留原紀錄並排除上述合計。</Notice>}
      <div className="two-col section-gap">{["estimated", "actual"].map(phase => {
        const margin = data.data?.margin; const amount = margin?.[`${phase}_gross_margin_minor`]; const reason = margin?.[`${phase}_reason`];
        return <div className="selection-summary" key={phase}><strong>{phase === "estimated" ? "預估毛利" : "目前登錄成本毛利"}</strong><span>{amount == null ? "資料不足，無法計算" : `${margin.currency} ${(amount / 100).toLocaleString(undefined, { minimumFractionDigits: 2 })}`}</span><small>{amount == null ? marginReasons[reason] || "請核對合約與完整成本資料" : margin.basis}</small></div>;
      })}</div>
    </>}
  </Card><Card title="新增工時與成本"><form className="form-stack" onChange={() => { setDirty(true); action.clear(); }} onSubmit={async event => { event.preventDefault(); const form = new FormData(event.currentTarget); const result = await action.mutate(path, { phase: form.get("phase"), category: form.get("category"), minutes: Number(form.get("minutes")), cost_minor: priced ? Math.round(Number(form.get("amount")) * 100) : null, currency: priced ? String(form.get("currency")).toUpperCase() : null, task_id: optional(form, "task_id"), note: String(form.get("note")).trim() }); if (result) { setDirty(false); data.reload(); } }}>
    <div className="form-grid"><label>階段<select name="phase"><option value="estimated">預估</option><option value="actual">實際</option></select></label><label>分類<select name="category">{Object.entries(costCategories).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label><label>工時（分鐘）<input name="minutes" required type="number" min={0} max={10000000} step={1} /></label><label>關聯待辦編號（選填）<input name="task_id" /></label></div><label className="answer-option"><input type="checkbox" checked={priced} onChange={event => setPriced(event.target.checked)} />已取得明確的本筆總金額</label>
    {priced && <div className="form-grid"><label>本筆總金額（元）<input name="amount" type="number" min={0} max={20000000} step={0.01} required /></label><label>幣別（3 碼大寫）<input name="currency" required pattern="[A-Z]{3}" maxLength={3} defaultValue="TWD" /></label></div>}<label>成本或工時依據<textarea name="note" required maxLength={1000} rows={3} /></label><button className="button" disabled={action.pending || !!action.result}>確認新增紀錄</button><MutationStatus action={action} success="工時與成本已新增；合計已重新讀取。" />
  </form></Card>{selected && <Card title="作廢原紀錄，保留歷史"><form className="form-stack" onSubmit={async event => { event.preventDefault(); const form = new FormData(event.currentTarget); if (await voidAction.mutate(`/internal/costs/${selected.id}/void`, { reason: String(form.get("reason")).trim() })) { setSelected(null); data.reload(); } }}><p>{selected.note} · {selected.minutes} 分鐘</p><label>作廢原因<textarea name="reason" required maxLength={1000} rows={3} /></label><label className="answer-option"><input type="checkbox" required />確認保留原紀錄並排除本筆合計，需要更正時另建正確紀錄。</label><button className="button button-secondary" disabled={voidAction.pending}>確認作廢此筆紀錄</button><MutationStatus action={voidAction} /></form></Card>}</div>;
}

export function ProjectCostsPage() {
  const [page, setPage] = useState(1); const [selected, setSelected] = useState<Row | null>(null); const projects = useResource(`/internal/cost-projects?page=${page}&page_size=20`);
  return <><PageHeading title="專案工時與成本" description="財務與 PM 僅能處理已有專案授權的成本，未定價與各幣別分別追蹤。" /><div className="section-stack"><Card title="選擇授權專案">{projects.loading ? <Loading /> : projects.error ? <ErrorState error={projects.error} retry={projects.reload} /> : <DataTable rows={items(projects.data)} title="成本專案" page={page} total={projects.data?.total} onPage={setPage} columns={[{ key: "name", title: "專案" }, { key: "year", title: "年度" }, { key: "action", title: "查看", render: row => <button className="button button-secondary button-small" onClick={() => { if (confirmFormNavigation()) setSelected(row); }}>查看工時與成本</button> }]} />}</Card>{selected && <div><h2>{selected.name}</h2><ProjectCosts key={selected.id} projectId={selected.id} /></div>}</div></>;
}
