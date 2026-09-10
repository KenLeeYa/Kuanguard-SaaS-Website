"use client";

import { useState } from "react";
import { dateTime, items, useMutation, useResource, useSession, type Row } from "@/lib/api";
import { Badge, Card, DataTable, ErrorState, Loading, MutationStatus, Notice } from "./ui";

const classifications: Record<string, string> = { confirmed_human: "已確認人類互動", automated: "自動設備／掃描器", ambiguous: "資訊不足，無法確認" };
const eventLabels: Record<string, string> = { clicked_candidate: "點擊候選", human_interaction: "互動候選", opened: "開信訊號", delivered: "送達回報", bounced: "退信", reported: "安全回報" };

export function CampaignEvents({ campaign, reload }: { campaign: Row; reload: () => void }) {
  const [selected, setSelected] = useState<Row | null>(null);
  const review = useMutation();
  return <>
    <Card title="原始事件與人工判讀">
      <Notice>指標以不重複的規劃訊息計算。同一封信的多次點擊不會重複計數；開信與點擊候選仍需核對來源，不能直接視為人類操作。</Notice>
      <DataTable rows={items(campaign.events)} title="活動原始事件" columns={[
        { key: "event_type", title: "事件類型", render: r => eventLabels[r.event_type] || r.event_type },
        { key: "message_id", title: "訊息識別碼" },
        { key: "source", title: "來源" },
        { key: "classification", title: "目前判讀", render: r => <Badge tone={r.classification === "confirmed_human" ? "success" : "neutral"}>{classifications[r.classification] || "待判讀"}</Badge> },
        { key: "occurred_at", title: "發生時間", render: r => dateTime(r.occurred_at) },
        { key: "review", title: "操作", render: r => ["clicked_candidate", "human_interaction"].includes(r.event_type) && r.id ? <button className="button button-secondary button-small" disabled={review.pending} onClick={() => { setSelected(r); review.clear(); }}>判讀此事件</button> : "此事件無需人工分類" },
      ]} />
      {selected && <form key={selected.id} className="form-stack section-gap" onChange={review.clear} onSubmit={async e => {
        e.preventDefault();
        const form = new FormData(e.currentTarget);
        if (await review.mutate(`/customer/campaigns/${campaign.id}/events/${selected.id}/review`, { classification: form.get("classification"), reason: String(form.get("reason")).trim() })) reload();
      }}>
        <div className="selection-summary"><strong>判讀事件：{eventLabels[selected.event_type] || selected.event_type}</strong><span>訊息：{selected.message_id}</span><span>事件時間：{dateTime(selected.occurred_at)}（Asia/Taipei）</span></div>
        <label>核對結果<select name="classification" defaultValue={classifications[selected.classification] ? selected.classification : "ambiguous"} required>{Object.entries(classifications).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>判讀依據（至少 10 字）<textarea name="reason" minLength={10} maxLength={2000} rows={4} required placeholder="例如：受測者確認、郵件閘道紀錄或無法排除自動設備的原因。請勿填寫密碼。" /></label>
        <p className="form-help">系統保留真實操作者、分類變更與依據。確認為人類互動後，可由具派課權限的管理者另行確認補救訓練。</p>
        <div className="actions"><button className="button" disabled={review.pending}>儲存事件判讀</button><button className="button button-secondary" type="button" disabled={review.pending} onClick={() => { setSelected(null); review.clear(); }}>取消</button></div>
        <MutationStatus action={review} />
      </form>}
    </Card>
    <Remediation campaign={campaign} />
  </>;
}

function Remediation({ campaign }: { campaign: Row }) {
  const { session } = useSession();
  const permitted = !!session?.roles.includes("training_manager");
  const catalog = useResource(permitted && campaign.remediation_course_id ? "/customer/training/courses?page_size=100" : null);
  const action = useMutation();
  const [confirmed, setConfirmed] = useState(false);
  if (!campaign.remediation_course_id) return <Card title="補救教育訓練"><Notice>本活動尚未指定補救課程。建立活動時可選擇課程，並由具教育訓練權限的管理者確認派課。</Notice></Card>;
  if (!permitted) return <Card title="補救教育訓練"><Notice>本活動已指定補救課程；執行補救派課需同時具備活動管理與教育訓練管理權限。</Notice></Card>;
  const course = items(catalog.data).find(c => c.id === campaign.remediation_course_id);
  return <Card title="確認補救派課">
    {catalog.loading ? <Loading /> : catalog.error ? <ErrorState error={catalog.error} retry={catalog.reload} /> : !course ? <Notice tone="warning">指定課程目前無法取得，請先確認課程授權與可用狀態。</Notice> : <form className="form-stack" onSubmit={async e => { e.preventDefault(); await action.mutate(`/customer/campaigns/${campaign.id}/remediation`); }}>
      <div className="selection-summary"><strong>{course.title}</strong><span>優先使用適用席次；無席次時每份授權 {course.points} 點，首次啟動後耗用。</span><span>已確認人類互動：{campaign.metrics?.confirmed_human_interaction ?? "待核對"} 封不同訊息。</span><span>僅處理已確認人類互動且已連結學員的受測者；既有有效授權不重複預留；席次與點數分開核對。</span></div>
      <label className="answer-option"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} required />我已核對分類與課程，確認為符合條件的學員建立補救授權及預留適用席次或點數。</label>
      <button className="button" disabled={!confirmed || action.pending || !!action.result || !campaign.metrics?.confirmed_human_interaction}>確認補救派課與授權預留</button>
      <MutationStatus action={action} success="補救授權已由後端核對。" />
      {action.result && <Notice tone="success">本次確認授權 {items(action.result).length} 份；另有 {action.result.unlinked_recipients ?? 0} 位受測者尚未連結學員，未建立授權。</Notice>}
    </form>}
  </Card>;
}
