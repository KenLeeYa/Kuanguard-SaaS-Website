"use client";

import { useState } from "react";
import { dateTime, items, useMutation, useResource, type Row } from "@/lib/api";
import { Card, DataTable, ErrorState, Loading, MutationStatus, Notice, PageHeading, Status } from "./ui";

export const trainingSources: Record<string, string> = { annual_included: "年度合約內含席次", gift: "贈送席次", manual: "人工核定席次", points: "企業點數", point: "企業點數" };
export function AuthorizationSummary({ authorization }: { authorization: Row }) {
  return <div className="selection-summary"><strong>授權來源：{trainingSources[authorization.source] || authorization.source || "依後端核定"}</strong><span>{authorization.unit === "enrollment_seat" ? `本次使用 ${authorization.quantity} 份有限開課席次` : `本次使用 ${authorization.quantity} 點`}</span><span>有效期限：{dateTime(authorization.expires_at)}（Asia/Taipei）</span><span>未啟動取消或到期可釋放原預留；開始後保留使用紀錄，續看不重複扣帳。</span></div>;
}

export function TrainingLicenses({ internal = false }: { internal?: boolean }) {
  const [page, setPage] = useState(1);
  const [source, setSource] = useState("manual");
  const data = useResource(`/${internal ? "internal" : "customer"}/training/entitlements?page=${page}&page_size=20`);
  const courses = useResource(internal ? "/internal/training/courses?page_size=100" : null);
  const contracts = useResource(internal ? "/internal/training/contracts?page_size=100" : null);
  const action = useMutation();
  return <>
    {internal && <PageHeading title="教育訓練席次核定" description="以有限的年度、贈送或人工授權席次管理開課，與企業點數分開記帳。" />}
    <div className="section-stack"><Notice>席次是有限累計開課授權。只有尚未啟動的取消或到期授權可釋放；已啟動授權不會回補成可無限重用席次。</Notice>
      <Card title="課程授權與剩餘席次">{data.loading ? <Loading /> : data.error ? <ErrorState error={data.error} retry={data.reload} /> : <DataTable rows={items(data.data)} page={page} total={data.data?.total} onPage={setPage} title="課程授權席次" columns={[
        { key: "course_title", title: "課程" }, { key: "source", title: "來源", render: row => trainingSources[row.source] || row.source }, { key: "cohort", title: "適用梯次", render: row => row.cohort || "所有梯次" }, { key: "quantity", title: "原核定席次" }, { key: "available", title: "可用席次" }, { key: "reserved", title: "已預留" }, { key: "consumed", title: "已啟動耗用" }, { key: "released", title: "歷次釋放" }, { key: "expires_at", title: "授權期限", render: row => <>{dateTime(row.starts_at)}<br />至 {dateTime(row.expires_at)}</> }, { key: "status", title: "狀態", render: row => <Status value={row.status} /> },
      ]} />}</Card>
      {internal && <Card title="核發有限課程席次"><form className="form-stack" onChange={action.clear} onSubmit={async event => {
        event.preventDefault(); const form = new FormData(event.currentTarget);
        const result = await action.mutate("/internal/training/entitlements", { course_id: form.get("course_id"), source, quantity: Number(form.get("quantity")), starts_at: new Date(String(form.get("starts_at"))).toISOString(), expires_at: new Date(String(form.get("expires_at"))).toISOString(), cohort: String(form.get("cohort") || "").trim() || null, contract_id: source === "annual_included" ? form.get("contract_id") : null, source_reference: String(form.get("source_reference")).trim(), reason: String(form.get("reason")).trim() });
        if (result) data.reload();
      }}>
        {courses.error && <ErrorState error={courses.error} retry={courses.reload} />}
        <div className="form-grid"><label>課程<select name="course_id" required><option value="">選擇課程</option>{items(courses.data).map(course => <option key={course.id} value={course.id}>{course.title} · v{course.version}</option>)}</select></label><label>核定來源<select value={source} onChange={event => setSource(event.target.value)}><option value="manual">人工核定</option><option value="gift">贈送</option><option value="annual_included">年度合約內含</option></select></label><label>有限席次數<input name="quantity" type="number" min={1} max={100000} step={1} required /></label><label>適用梯次（空白為不限梯次）<input name="cohort" maxLength={40} /></label><label>生效時間（裝置本地時間）<input name="starts_at" type="datetime-local" required /></label><label>到期時間（裝置本地時間）<input name="expires_at" type="datetime-local" required /></label></div>
        {source === "annual_included" && <>{contracts.error ? <ErrorState error={contracts.error} retry={contracts.reload} /> : <label>目前企業的有效合約<select name="contract_id" required><option value="">選擇有效合約</option>{items(contracts.data).map(contract => <option key={contract.id} value={contract.id}>{contract.title} · v{contract.version}</option>)}</select></label>}</>}
        <label>核定來源／文件編號<input name="source_reference" required maxLength={200} /></label><label>核定原因<textarea name="reason" required maxLength={1000} rows={3} /></label>
        <label className="answer-option"><input type="checkbox" required />我已核對來源、期間與有限席次；年度內含授權已連結本企業有效合約。</label><button className="button" disabled={action.pending || !!action.result || courses.loading || !!courses.error || (source === "annual_included" && (contracts.loading || !!contracts.error))}>確認核發有限席次</button><MutationStatus action={action} success="有限課程席次已核發並記錄核定依據。" />
      </form></Card>}
    </div>
  </>;
}
