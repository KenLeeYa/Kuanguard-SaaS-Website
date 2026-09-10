"use client";

import { useState } from "react";
import { dateTime, items, useMutation, useResource, useSession, type Row } from "@/lib/api";
import { Card, DataTable, ErrorState, Loading, Metric, MutationStatus, Notice, PageHeading, Status } from "./ui";

const exportSections = [
  { key: "projects", label: "授權專案", roles: ["customer_contact"] }, { key: "reports", label: "已發布報告紀錄", roles: ["customer_contact"] }, { key: "findings", label: "已發布檢測結果", roles: ["customer_contact"] }, { key: "orders", label: "購點訂單", roles: ["billing_manager"] }, { key: "training", label: "教育授權紀錄", roles: ["training_manager"] }, { key: "campaigns", label: "自己的演練活動", roles: ["campaign_manager"] }, { key: "tickets", label: "自己的工單", roles: ["customer_admin", "customer_contact", "campaign_manager", "training_manager", "billing_manager", "learner"] },
];

export function CustomerDataPage() {
  const { session } = useSession();
  const [section, setSection] = useState("");
  const [cursors, setCursors] = useState([0]);
  const cursor = cursors[cursors.length - 1];
  const data = useResource(section ? `/customer/data-export?section=${section}&cursor=${cursor}` : null);
  const requests = useResource(session?.roles.includes("customer_admin") ? "/customer/lifecycle/requests" : null);
  const action = useMutation();
  return <><PageHeading title="資料匯出與退場申請" description="依目前角色取得授權資料；保存、結清與企業退場透過具體申請及作業審核處理。" /><div className="section-stack">
    <Card title="分頁匯出授權資料"><div className="form-stack"><label>授權資料類別<select value={section} onChange={event => { setSection(event.target.value); setCursors([0]); }}><option value="">請選擇要匯出的類別</option>{exportSections.filter(item => item.roles.some(role => session?.roles.includes(role))).map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
      <Notice>每次只下載目前一頁，最多 200 筆。下載內容限此類別、目前企業及角色授權，不能視為所有企業資料或全部報告檔案的完整備份。</Notice>
      {data.loading ? <Loading /> : data.error ? <ErrorState error={data.error} retry={data.reload} /> : data.data && <><div className="selection-summary"><strong>第 {cursors.length} 頁：{items(data.data).length} 筆</strong><span>產生時間：{dateTime(data.data.generated_at)}（Asia/Taipei）</span><span>{data.data.next_cursor === null ? "此類別目前沒有下一頁。" : "還有下一頁；目前下載不包含後續資料。"}</span></div><div className="actions"><button className="button" onClick={() => {
        const blob = new Blob([JSON.stringify(data.data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = `kuanguard-${section}-cursor-${cursor}.json`; link.click(); URL.revokeObjectURL(url);
      }}>下載目前這一頁 JSON</button><button className="button button-secondary" disabled={cursors.length <= 1} onClick={() => setCursors(value => value.slice(0, -1))}>上一頁</button><button className="button button-secondary" disabled={data.data.next_cursor === null} onClick={() => setCursors(value => [...value, Number(data.data?.next_cursor)])}>取得下一頁</button></div></>}
    </div></Card>
    {session?.roles.includes("customer_admin") && <>
      <Card title="提出資料／企業退場申請"><form className="form-stack" onChange={action.clear} onSubmit={async event => { event.preventDefault(); const form = new FormData(event.currentTarget); if (await action.mutate("/customer/lifecycle/requests", { kind: form.get("kind"), reason: String(form.get("reason")).trim() })) requests.reload(); }}><label>申請類型<select name="kind" required><option value="data_export">協助資料匯出</option><option value="tenant_offboard">企業退場評估</option></select></label><label>需求與原因<textarea name="reason" required minLength={5} maxLength={1000} rows={4} /></label><Notice>提出申請不會直接撤銷存取或刪除資料。退場需核對執行中工作、寄送對帳、財務及保存條款；本機保存政策尚待正式核定。</Notice><button className="button" disabled={action.pending || !!action.result}>確認提出申請</button><MutationStatus action={action} success="申請已記錄，等待作業審核。" /></form></Card>
      <Card title="我的申請紀錄">{requests.loading ? <Loading /> : requests.error ? <ErrorState error={requests.error} retry={requests.reload} /> : <DataTable rows={items(requests.data)} title="資料與退場申請" columns={[{ key: "data_class", title: "類型", render: row => row.data_class === "tenant_offboard" ? "企業退場" : "資料匯出" }, { key: "reason", title: "原因", render: row => <p>{row.reason}</p> }, { key: "status", title: "狀態", render: row => <Status value={row.status} /> }, { key: "created_at", title: "申請時間", render: row => dateTime(row.created_at) }]} />}</Card>
    </>}
  </div></>;
}

export function InternalLifecycle() {
  const data = useResource("/internal/lifecycle");
  const { session } = useSession();
  const plan = useMutation();
  const execute = useMutation();
  const [confirmedName, setConfirmedName] = useState("");
  const manifest: Row | undefined = plan.result?.manifest;
  const blocked = !!manifest && (items(manifest.blocking_running_jobs).length > 0 || items(manifest.blocking_unknown_messages).length > 0);
  return <><PageHeading title="企業退場作業審核" description="此頁須同時具備 PM 與財務角色；先產生具體計畫並核對阻擋項目，再由操作者明確確認。" /><div className="section-stack">
    <Notice tone="warning">退場會撤銷客戶與學員存取、取消尚未開始的作業並釋放適用預留。報告、帳本、完課與結清歷史仍保留；本操作不刪除資料。</Notice>
    <Card title="企業狀態與申請">{data.loading ? <Loading /> : data.error ? <ErrorState error={data.error} retry={data.reload} /> : <><p>目前企業：{session?.tenant.name} · <Status value={data.data?.tenant_status} /></p><DataTable rows={items(data.data?.requests)} title="待審核退場申請" columns={[{ key: "data_class", title: "類型", render: row => row.data_class === "tenant_offboard" ? "企業退場" : "資料匯出" }, { key: "reason", title: "原因", render: row => <p>{row.reason}</p> }, { key: "status", title: "狀態", render: row => <Status value={row.status} /> }, { key: "plan", title: "操作", render: row => row.data_class === "tenant_offboard" && row.status === "requested" ? <button className="button button-secondary button-small" disabled={plan.pending || execute.pending} onClick={async () => { setConfirmedName(""); execute.clear(); await plan.mutate("/internal/lifecycle/plan", { request_id: row.id }); }}>產生退場計畫</button> : "依目前申請狀態處理" }]} /></>}</Card>
    <MutationStatus action={{ ...plan, result: null }} />
    {manifest && <Card title="待人工確認的退場計畫"><div className="form-stack"><p>計畫期限：{dateTime(plan.result?.expires_at)}（Asia/Taipei）</p><div className="metrics"><Metric label="執行中工作" value={items(manifest.blocking_running_jobs).length} detail="須先等待完成" /><Metric label="未知寄送" value={items(manifest.blocking_unknown_messages).length} detail="須先完成供應商對帳" /><Metric label="尚未啟動授權" value={manifest.unstarted_enrollments} detail="將依規則釋放預留" /><Metric label="尚未寄送訊息" value={manifest.planned_messages} detail="將停止寄送並處理預留" /></div>
      {blocked ? <Notice tone="warning">目前有執行中工作或未知寄送，不能執行退場。處理完成後重新產生計畫。</Notice> : <Notice>此計畫只適用目前狀態。內容變動或期限過後，伺服器會拒絕套用，需重新產生計畫。</Notice>}
      <form className="form-stack" onSubmit={async event => { event.preventDefault(); if (confirmedName !== session?.tenant.name) return; const result = await execute.mutate("/internal/lifecycle/offboard", { plan_id: plan.result?.id, expected_digest: plan.result?.digest, confirmation: "REVOKE_CUSTOMER_ACCESS_KEEP_DATA" }); if (result) data.reload(); }}>
        <label>輸入目前企業名稱以確認<input value={confirmedName} onChange={event => setConfirmedName(event.target.value)} required autoComplete="off" /></label><label className="answer-option"><input type="checkbox" required />我已檢視本次計畫，確認撤銷此企業客戶存取，並保留報告、帳本與歷史資料。</label>
        <button className="button button-danger" disabled={blocked || execute.pending || !!execute.result || confirmedName !== session?.tenant.name || new Date(String(plan.result?.expires_at)).getTime() <= Date.now()}>確認執行本次企業退場</button>
      </form><MutationStatus action={execute} success="企業退場狀態已更新，資料仍保留。" /><p className="form-help">計畫編號：{plan.result?.id} · 摘要：{plan.result?.digest}</p>
    </div></Card>}
  </div></>;
}
