"use client";

import Link from "./guarded-link";
import { useState } from "react";
import { dateTime, items, useDirtyForm, useMutation, useResource, type Row } from "@/lib/api";
import { Badge, ButtonLink, Card, DataTable, ErrorState, Loading, MutationStatus, Notice, PageHeading, Status } from "./ui";

const reviewLabels: Record<string, string> = { unreviewed: "待覆核", reviewed: "已覆核", needs_revision: "需補充", insufficient_evidence: "證據不足", open: "待填寫", in_review: "覆核中" };

export function Questionnaires({ id, internal = false }: { id?: string; internal?: boolean }) {
  const [page, setPage] = useState(1);
  const [create, setCreate] = useState(false);
  const prefix = internal ? "/internal" : "/customer";
  const uiPrefix = internal ? "/admin" : "";
  const data = useResource(id ? `${prefix}/questionnaires/${id}` : `${prefix}/questionnaires?page=${page}&page_size=20`);
  const action = useMutation();
  return <>
    <PageHeading title={id ? data.data?.title || "資安問卷" : internal ? "問卷證據覆核" : "資安問卷與證據"} description="填寫企業／供應商問卷並留下證據參考與覆核版本。問卷到期提醒不代表自動核准或認證。" action={!id && !internal ? <button className="button" onClick={() => setCreate(!create)}>建立問卷</button> : id ? <ButtonLink href={`${uiPrefix}/questionnaires`} secondary>返回問卷列表</ButtonLink> : undefined} />
    <div className="section-stack">
      {!id && create && !internal && <Card title="建立企業問卷"><form className="form-stack" onChange={action.clear} onSubmit={async e => {
        e.preventDefault();
        const form = new FormData(e.currentTarget);
        const result = await action.mutate("/customer/questionnaires", { title: form.get("title"), supplier: form.get("supplier"), due_at: new Date(String(form.get("due_at"))).toISOString(), questions: String(form.get("questions")).split(/\r?\n/).map(s => s.trim()).filter(Boolean) });
        if (result) data.reload();
      }}>
        <div className="form-grid"><label>問卷名稱<input name="title" required maxLength={120} /></label><label>受評企業／供應商<input name="supplier" required maxLength={120} /></label><label>預定期限（裝置本地時間）<input name="due_at" type="datetime-local" required /></label></div>
        <label>問題清單（每行一題，最多 100 題）<textarea name="questions" rows={6} required maxLength={200000} placeholder={"是否定期覆核帳號權限？\n請說明備份與還原演練方式。"} /></label>
        <button className="button" disabled={action.pending || !!action.result}>確認建立問卷</button><MutationStatus action={action} />{action.result?.id && <ButtonLink href={`/questionnaires/${action.result.id}`}>填寫此問卷</ButtonLink>}
      </form></Card>}
      {data.loading ? <Loading /> : data.error ? <ErrorState error={data.error} retry={data.reload} /> : id && data.data ? <>
        <Card title="問卷資訊"><div className="selection-summary"><strong>{data.data.supplier}</strong><span>期限：{dateTime(data.data.due_at)}（Asia/Taipei）</span><span>上次載入狀態：{reviewLabels[data.data.status] || data.data.status}{data.data.overdue ? " · 已逾期" : ""}</span></div><Notice>證據參考僅記錄文字，請填寫文件編號、核定紀錄或必要說明。系統不會開啟外部來源，不接受密碼或原始掃描檔上傳。</Notice></Card>
        {items(data.data.answers).map(answer => <QuestionnaireAnswer key={answer.id} entry={answer} questionnaireId={id} internal={internal} />)}
      </> : <Card title="目前企業問卷"><DataTable rows={items(data.data)} page={page} total={data.data?.total} onPage={setPage} title="資安問卷" columns={[
        { key: "title", title: "問卷", render: r => <Link href={`${uiPrefix}/questionnaires/${r.id}`}>{r.title}</Link> },
        { key: "supplier", title: "受評企業／供應商" },
        { key: "status", title: "狀態", render: r => <Badge>{reviewLabels[r.status] || r.status}</Badge> },
        { key: "due_at", title: "期限", render: r => <>{dateTime(r.due_at)}{r.overdue && <Badge tone="warning">已逾期</Badge>}</> },
      ]} /></Card>}
    </div>
  </>;
}

function QuestionnaireAnswer({ entry, questionnaireId, internal }: { entry: Row; questionnaireId: string; internal: boolean }) {
  const [current, setCurrent] = useState(entry);
  const [dirty, setDirty] = useState(false);
  const action = useMutation();
  useDirtyForm(dirty);
  return <Card title={current.question} aside={<Badge tone={current.review_status === "reviewed" ? "success" : "neutral"}>{reviewLabels[current.review_status] || current.review_status}</Badge>}>
    <form className="form-stack" onChange={() => { setDirty(true); action.clear(); }} onSubmit={async e => {
      e.preventDefault();
      const form = new FormData(e.currentTarget);
      const body = internal ? { decision: form.get("decision"), reason: String(form.get("reason")).trim(), expected_revision: current.revision } : { answer: String(form.get("answer")).trim(), evidence_reference: String(form.get("evidence_reference")).trim(), expected_revision: current.revision };
      const result = await action.mutate(`${internal ? "/internal" : "/customer"}/questionnaires/${questionnaireId}/answers/${current.id}${internal ? "/review" : ""}`, body);
      if (result) { const updated = items(result.answers).find(answer => answer.id === current.id); if (updated) setCurrent(updated); setDirty(false); }
    }}>
      {internal ? <>
        <div className="selection-summary"><strong>企業回覆</strong><p className="preserve-lines">{current.answer || "尚未填寫"}</p><strong>證據參考</strong><p className="preserve-lines">{current.evidence_reference || "尚未提供"}</p></div>
        <label>覆核結論<select name="decision" defaultValue="insufficient_evidence" required><option value="insufficient_evidence">證據不足</option><option value="needs_revision">需要補充或修訂</option><option value="reviewed" disabled={!current.answer || !current.evidence_reference}>回覆與證據已覆核</option></select></label>
        <label>覆核依據<textarea name="reason" required maxLength={1000} rows={3} /></label>
      </> : <>
        <label>企業回覆<textarea name="answer" defaultValue={current.answer} required maxLength={10000} rows={4} /></label>
        <label>證據參考文字（選填，未提供時不能核定證據已覆核）<textarea name="evidence_reference" defaultValue={current.evidence_reference} maxLength={2000} rows={3} /></label>
      </>}
      <p className="form-help">送出時會檢查原始版本；若他人已更新，請保留您的內容並重新載入最新資料後再核對。</p>
      <button className="button" disabled={action.pending || (!!action.result && !dirty)}>{internal ? "儲存證據覆核" : "儲存回覆與證據參考"}</button>
      <MutationStatus action={action} success={internal ? "覆核結論與依據已記錄。" : "回覆已儲存，等待證據覆核。"} />
    </form>
  </Card>;
}

export function NotificationsPage() {
  const [page, setPage] = useState(1);
  const data = useResource(`/customer/notifications?page=${page}&page_size=20`);
  const action = useMutation();
  return <><PageHeading title="我的通知" description="僅顯示目前登入使用者收到的通知；已讀狀態不影響其他成員。" /><Card title="個人通知">{data.loading ? <Loading /> : data.error ? <ErrorState error={data.error} retry={data.reload} /> : <DataTable rows={items(data.data)} page={page} total={data.data?.total} onPage={setPage} title="個人通知" columns={[
    { key: "title", title: "通知", render: r => <><strong>{r.title}</strong><p className="preserve-lines">{r.text}</p></> },
    { key: "created_at", title: "收到時間", render: r => dateTime(r.created_at) },
    { key: "is_read", title: "狀態", render: r => r.is_read ? <Badge>已讀</Badge> : <Badge tone="warning">未讀</Badge> },
    { key: "read", title: "操作", render: r => r.is_read ? dateTime(r.read_at) : <button className="button button-secondary button-small" disabled={action.pending} onClick={async () => { if (await action.mutate(`/customer/notifications/${r.id}/read`)) data.reload(); }}>標示已讀</button> },
  ]} />}<MutationStatus action={action} success="此則通知已標示為已讀。" /></Card></>;
}

export function TicketsPage({ id, internal = false }: { id?: string; internal?: boolean }) {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [replyText, setReplyText] = useState("");
  const [visibility, setVisibility] = useState("customer");
  const data = useResource(id ? `${internal ? "/internal" : "/customer"}/tickets/${id}` : `/internal/tickets?page=${page}&page_size=20`);
  const action = useMutation();
  const reply = useMutation();
  useDirtyForm(!!replyText);
  return <>
    <PageHeading title={id ? data.data?.subject || "工單內容" : "企業支援工單"} description={internal ? "PM 依原始需求記錄處理進度；變更前核對最新狀態。" : "查看自己提出的原始需求與目前處理狀態。"} action={id ? <ButtonLink href={internal ? "/admin/tickets" : "/support"} secondary>返回工單列表</ButtonLink> : undefined} />
    {data.loading ? <Loading /> : data.error ? <ErrorState error={data.error} retry={data.reload} /> : id && data.data ? <div className="section-stack">
      <Card title="原始需求"><p><Status value={data.data.status} /> · {dateTime(data.data.created_at)}（Asia/Taipei）</p><p className="preserve-lines">{data.data.text}</p></Card>
      <Card title="工單對話與處理紀錄"><div className="section-stack">{items(data.data.messages).map(message => <article className="selection-summary" key={message.id}><strong>{message.visibility === "internal" ? "內部備註" : message.from_support ? "服務團隊" : "需求提出者"}</strong><span>{dateTime(message.created_at)}（Asia/Taipei）</span><p className="preserve-lines">{message.text}</p></article>)}{!items(data.data.messages).length && <Notice>目前尚無對話紀錄。</Notice>}</div></Card>
      <Card title={internal ? "回覆或留下內部備註" : "補充工單說明"}><form className="form-stack" onSubmit={async event => {
        event.preventDefault();
        const result = await reply.mutate(`/${internal ? "internal" : "customer"}/tickets/${id}/messages`, { text: replyText, visibility: internal ? visibility : "customer" });
        if (result) { setReplyText(""); data.reload(); }
      }}>
        {internal && <label>可見範圍<select value={visibility} onChange={event => { setVisibility(event.target.value); reply.clear(); }}><option value="customer">回覆客戶</option><option value="internal">僅內部 PM 備註</option></select></label>}
        <label>文字內容<textarea value={replyText} onChange={event => { setReplyText(event.target.value); reply.clear(); }} required maxLength={10000} rows={4} disabled={reply.pending} /></label>
        {internal && visibility === "internal" && <Notice>此備註僅供內部作業，客戶對話不會顯示。</Notice>}
        {data.data.status === "closed" && <Notice tone="warning">此工單已結案，目前不能新增對話。此頁輸入仍保留，請先確認處理狀態。</Notice>}
        <button className="button" disabled={reply.pending || data.data.status === "closed"}>{internal && visibility === "internal" ? "記錄內部備註" : "送出對話內容"}</button><MutationStatus action={reply} success="文字內容已加入工單對話。" />
      </form></Card>
      {internal && <Card title="更新處理狀態"><form className="form-stack" onChange={action.clear} onSubmit={async e => {
        e.preventDefault(); const form = new FormData(e.currentTarget);
        if (await action.mutate(`/internal/tickets/${id}/status`, { status, reason: String(form.get("reason")).trim(), expected_status: data.data?.status })) { setStatus(""); data.reload(); }
      }}><label>新狀態<select value={status} onChange={e => setStatus(e.target.value)} required><option value="">請選擇</option><option value="open">待處理</option><option value="in_progress">處理中</option><option value="closed">已結案</option></select></label><label>處理依據與原因<textarea name="reason" required maxLength={1000} rows={4} /></label><button className="button" disabled={action.pending || !status || status === data.data.status}>確認更新工單狀態</button></form></Card>}
      <MutationStatus action={action} success="工單狀態與操作依據已記錄。" />
    </div> : <Card title="目前企業工單"><DataTable rows={items(data.data)} page={page} total={data.data?.total} onPage={setPage} title="企業支援工單" columns={[
      { key: "subject", title: "主旨", render: r => <Link href={`/admin/tickets/${r.id}`}>{r.subject}</Link> },
      { key: "status", title: "狀態", render: r => <Status value={r.status} /> },
      { key: "created_at", title: "提出時間", render: r => dateTime(r.created_at) },
    ]} /></Card>}
  </>;
}
