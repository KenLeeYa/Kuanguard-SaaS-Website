"use client";

import { useState } from "react";
import { ApiError, confirmFormNavigation, items, useDirtyForm, useMutation, useResource, useSession, type Row } from "@/lib/api";
import { Card, DataTable, ErrorState, Loading, MutationStatus, Notice, PageHeading } from "./ui";

export function LearnerManagement() {
  const data = useResource("/customer/training/learners?page_size=100");
  const { session } = useSession();
  const [selected, setSelected] = useState<Row | null>(null);
  const [operation, setOperation] = useState("department");
  const [department, setDepartment] = useState("");
  const [reason, setReason] = useState("");
  const action = useMutation();
  useDirtyForm(!!reason || (!!selected && department !== selected.department));
  function choose(row: Row) { if (!confirmFormNavigation()) return; setSelected(row); setDepartment(row.department || ""); setReason(""); action.clear(); }
  return <><PageHeading title="學員與部門管理" description="管理目前企業的學員身分。教育訓練管理者可查詢，企業管理者可更新部門及停用學員。" /><div className="section-stack">
    <Card title="目前有效學員">{data.loading ? <Loading /> : data.error ? <ErrorState error={data.error} retry={data.reload} /> : <DataTable rows={items(data.data)} title="目前企業學員" columns={[{ key: "name", title: "學員" }, { key: "email", title: "信箱" }, { key: "department", title: "部門" }, ...(session?.roles.includes("customer_admin") ? [{ key: "action", title: "管理", render: (row: Row) => <button className="button button-secondary button-small" disabled={action.pending} onClick={() => choose(row)}>部門與離職處理</button> }] : [])]} />}<p className="form-help">選單顯示本次取得的有效學員；停用後不再出現在有效名單。</p></Card>
    {selected && session?.roles.includes("customer_admin") && <Card title={`管理學員：${selected.name}`}><form className="form-stack" onSubmit={async event => { event.preventDefault(); const result = await action.mutate(`/customer/training/learners/${selected.id}/${operation}`, operation === "department" ? { department: department.trim(), expected_department: selected.department || "", reason: reason.trim() } : { reason: reason.trim() }); if (result) { setReason(""); setSelected(operation === "deactivate" ? null : result); setDepartment(result.department || ""); data.reload(); } }}>
      <label>操作<select value={operation} onChange={event => { setOperation(event.target.value); action.clear(); }}><option value="department">調整目前企業部門</option><option value="deactivate">停用目前企業學員身分</option></select></label>
      {operation === "department" ? <><label>新部門<input required maxLength={120} value={department} onChange={event => setDepartment(event.target.value)} /></label><p className="form-help">已讀取部門：{selected.department || "未設定"}。若其他人已更新，伺服器會拒絕覆寫。</p></> : <Notice tone="warning">只停用此企業的 learner membership，並釋放尚未啟動授權。其他角色、其他企業身分、已開始課程、證書及歷史紀錄仍保留。</Notice>}
      <label>處理原因<textarea required maxLength={1000} rows={3} value={reason} onChange={event => setReason(event.target.value)} /></label>
      {operation === "deactivate" && <label className="answer-option"><input type="checkbox" required />已核對姓名、信箱與目前企業，確認停用此學員身分。</label>}
      <button className="button" disabled={action.pending}>{operation === "department" ? "確認更新部門" : "確認停用學員身分"}</button>
      {action.error instanceof ApiError && action.error.status === 409 && <Notice tone="warning">資料已變更，您的輸入仍保留。請重新整理名單並比較新部門，再重新選取學員。<button type="button" className="button button-secondary section-gap" onClick={data.reload}>重新讀取名單</button></Notice>}
    </form></Card>}<MutationStatus action={action} success="學員管理操作已記錄；目前名單已重新讀取。" />
  </div></>;
}
