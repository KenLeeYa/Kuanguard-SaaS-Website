"use client";

import { useState } from "react";
import { dateTime, items, useMutation, useResource, useSession, type Row } from "@/lib/api";
import { localDateTime, useServerDraft } from "@/lib/use-server-draft";
import { DraftStatus } from "./draft-status";
import { AuthorizationSummary } from "./training-licenses";
import { ButtonLink, Card, ErrorState, Loading, MutationStatus, Notice, Status } from "./ui";

type CampaignDraft = { name: string; group_id: string; scheduled_at: string; remediation_course_id: string };
const campaignInitial: CampaignDraft = { name: "", group_id: "", scheduled_at: "", remediation_course_id: "" };
type TrainingDraft = { course_id: string; learner_id: string; cohort: string };
const trainingInitial: TrainingDraft = { course_id: "", learner_id: "", cohort: "2026" };
type PurchaseDraft = { points: number; order_id: string };
const purchaseInitial: PurchaseDraft = { points: 100, order_id: "" };

export function CampaignCreate() {
  const { session } = useSession();
  const groups = useResource("/customer/recipient-groups?page_size=100");
  const courses = useResource(session?.roles.includes("training_manager") ? "/customer/training/courses?page_size=100" : null);
  const draft = useServerDraft("campaign", campaignInitial);
  const [review, setReview] = useState<CampaignDraft | null>(null);
  const action = useMutation();
  const edit = (patch: Partial<CampaignDraft>) => { draft.edit({ ...draft.payload, ...patch }); setReview(null); action.clear(); };
  return <Card title="建立活動 · 草稿與範圍確認"><div className="form-stack">
    <DraftStatus draft={draft} describe={value => <><span>名稱：{value.name || "尚未填寫"}</span><span>群組：{items(groups.data).find(g => g.id === value.group_id)?.name || value.group_id || "尚未選擇"}</span><span>排程：{dateTime(value.scheduled_at)}</span><span>補救課程：{items(courses.data).find(c => c.id === value.remediation_course_id)?.title || value.remediation_course_id || "未指定"}</span></>} />
    <form className="form-stack" onSubmit={async e => { e.preventDefault(); if (await draft.saveNow()) setReview({ ...draft.payload }); }}>
      <fieldset className="form-stack draft-fields" disabled={!draft.initialized || draft.loading || action.pending || !!action.result}>
        <div className="form-grid"><label>活動名稱<input value={draft.payload.name || ""} onChange={e => edit({ name: e.target.value })} required maxLength={120} /></label><label>已授權受測群組<select value={draft.payload.group_id || ""} onChange={e => edit({ group_id: e.target.value })} required><option value="">請選擇群組</option>{items(groups.data).map(g => <option key={g.id} value={g.id}>{g.name}（{g.recipient_count} 人）</option>)}</select></label><label>寄送時間（此裝置本地時間）<input type="datetime-local" value={localDateTime(draft.payload.scheduled_at)} onChange={e => edit({ scheduled_at: e.target.value ? new Date(e.target.value).toISOString() : "" })} required /></label><label>補救課程（選填）<select value={draft.payload.remediation_course_id || ""} onChange={e => edit({ remediation_course_id: e.target.value })} disabled={!session?.roles.includes("training_manager")}><option value="">暫不指定</option>{items(courses.data).map(c => <option key={c.id} value={c.id}>{c.title}</option>)}</select></label></div>
        {groups.error && <ErrorState error={groups.error} retry={groups.reload} />}
        <p className="form-help">草稿不預留點數，也不寄送郵件。未建立群組時可先前往受測群組匯入授權名單，之後回到此表單恢復設定。</p>
        <button className="button button-secondary" disabled={!draft.ready || groups.loading || !!groups.error}>儲存並預覽活動設定</button>
      </fieldset>
    </form>
    {review && <div className="form-stack"><div className="selection-summary"><strong>{review.name}</strong><span>企業：{session?.tenant.name}</span><span>群組：{items(groups.data).find(g => g.id === review.group_id)?.name}</span><span>排程：{dateTime(review.scheduled_at)}（Asia/Taipei）</span><span>先建立活動，再於活動頁確認費率與點數預留。</span></div><button className="button" disabled={!draft.ready || action.pending || !!action.result} onClick={async () => { if (!await draft.saveNow()) return; const result = await action.mutate("/customer/campaigns", { name: review.name.trim(), group_id: review.group_id, scheduled_at: review.scheduled_at, ...(review.remediation_course_id ? { remediation_course_id: review.remediation_course_id } : {}) }); if (result) await draft.clear(); }}>確認建立活動</button></div>}
    <MutationStatus action={action} success="活動已建立，尚未寄送或預留點數。" />{action.result && <ButtonLink href={`/phishing/campaigns/${action.result.id}`}>查看活動並確認排程</ButtonLink>}
  </div></Card>;
}

export function EnrollmentForm() {
  const { session } = useSession();
  const courses = useResource("/customer/training/courses?page_size=100");
  const learners = useResource("/customer/training/learners?page_size=100");
  const draft = useServerDraft("training", trainingInitial);
  const [review, setReview] = useState<TrainingDraft | null>(null);
  const preview = useResource(review ? `/customer/training/assignment-preview?${new URLSearchParams({ course_id: review.course_id, learner_id: review.learner_id, cohort: review.cohort })}` : null);
  const action = useMutation();
  const edit = (patch: Partial<TrainingDraft>) => { draft.edit({ ...draft.payload, ...patch }); setReview(null); action.clear(); };
  const course = items(courses.data).find(c => c.id === review?.course_id);
  return <Card title="建立學習計畫與派課"><div className="form-stack">
    <DraftStatus draft={draft} describe={value => <><span>課程：{items(courses.data).find(c => c.id === value.course_id)?.title || value.course_id || "未選擇"}</span><span>學員：{items(learners.data).find(l => (l.id || l.user_id) === value.learner_id)?.name || value.learner_id || "未選擇"}</span><span>梯次：{value.cohort || "未填寫"}</span></>} />
    <form className="form-stack" onSubmit={async e => { e.preventDefault(); if (await draft.saveNow()) setReview({ ...draft.payload }); }}>
      <fieldset className="form-stack draft-fields" disabled={!draft.initialized || draft.loading || action.pending || !!action.result}>
        <label>課程<select value={draft.payload.course_id || ""} onChange={e => edit({ course_id: e.target.value })} required><option value="">選擇授權課程</option>{items(courses.data).map(c => <option key={c.id} value={c.id}>{c.title} · 無席次時 {c.points} 點</option>)}</select></label>
        <label>學員<select value={draft.payload.learner_id || ""} onChange={e => edit({ learner_id: e.target.value })} required><option value="">選擇企業學員</option>{items(learners.data).map(l => <option key={l.id || l.user_id} value={l.id || l.user_id}>{l.name} · {l.department || "企業成員"}</option>)}</select></label>
        <label>年度／梯次<input value={draft.payload.cohort || ""} onChange={e => edit({ cohort: e.target.value })} required maxLength={40} /></label>
        {(courses.error || learners.error) && <ErrorState error={(courses.error || learners.error)!} retry={() => { courses.reload(); learners.reload(); }} />}
        <Notice>系統優先核對適用的年度、贈送或人工席次。沒有適用席次時使用企業點數；已開始的授權不因重看而再次扣帳。</Notice>
        <button className="button button-secondary" disabled={!draft.ready || courses.loading || learners.loading || !!courses.error || !!learners.error}>儲存並預覽派課授權</button>
      </fieldset>
    </form>
    {review && (preview.loading ? <Loading /> : preview.error ? <ErrorState error={preview.error} retry={preview.reload} /> : preview.data && <div className="form-stack"><div className="selection-summary"><strong>{course?.title}</strong><span>企業：{session?.tenant.name}</span><span>學員：{items(learners.data).find(l => (l.id || l.user_id) === review.learner_id)?.name} · 梯次：{review.cohort}</span></div><AuthorizationSummary authorization={preview.data} />{preview.data.existing_enrollment_id ? <Notice>將沿用此學員的既有有效授權，不新增預留。</Notice> : <Notice>預覽不保留席次。確認時重新核對；若席次已用完，將按本課程 {course?.points} 點預留。請確認企業同意此授權與計費方式。</Notice>}<button className="button" disabled={!draft.ready || action.pending || !!action.result} onClick={async () => { if (!await draft.saveNow()) return; const result = await action.mutate("/customer/training/enrollments", review); if (result) await draft.clear(); }}>確認派課與授權方式</button></div>)}
    <MutationStatus action={action} success="派課已由後端核對，以下顯示本次實際授權來源。" />{action.result?.authorization && <AuthorizationSummary authorization={action.result.authorization} />}
  </div></Card>;
}

export function PurchaseForm({ wallet, refreshWallet }: { wallet: Row; refreshWallet: () => void }) {
  const draft = useServerDraft("purchase", purchaseInitial);
  const { session } = useSession();
  const [review, setReview] = useState(false);
  const create = useMutation();
  const settle = useMutation();
  const order = useResource(draft.payload.order_id ? `/customer/orders/${draft.payload.order_id}` : null);
  const paid = ["paid", "partially_refunded", "refunded"].includes(order.data?.status);
  return <Card title="購點與付款草稿"><div className="form-stack">
    <DraftStatus draft={draft} describe={value => <><span>點數包：{value.points} 點</span><span>訂單：{value.order_id || "尚未建立"}</span></>} />
    {!draft.payload.order_id ? <>
      <label>測試點數包<select value={draft.payload.points} disabled={!draft.initialized || draft.loading || create.pending} onChange={e => { draft.edit({ points: Number(e.target.value), order_id: "" }); setReview(false); create.clear(); settle.clear(); }}>{[100, 500, 1000].map(points => <option key={points} value={points}>{points.toLocaleString()} 點</option>)}</select></label>
      <p className="form-help">政策版本：{wallet.policy_version || "sandbox-v1"}。草稿不建立帳務，訂單與付款仍需分別確認。</p>
      {!review ? <button className="button button-secondary" disabled={!draft.ready} onClick={async () => { if (await draft.saveNow()) setReview(true); }}>儲存並查看購點確認</button> : <><div className="selection-summary"><strong>本次購點：{draft.payload.points} 點</strong><span>目前企業：{session?.tenant.name}</span><span>本機開發訂單，不扣取真實款項。點數條款與費率由後端隨訂單凍結。</span></div><button className="button" disabled={!draft.ready || create.pending || !!create.result} onClick={async () => { if (!await draft.saveNow()) return; const result = await create.mutate("/customer/wallet/orders", { points: draft.payload.points }); if (result) await draft.saveNow({ ...draft.payload, order_id: result.id }); }}>確認建立購點訂單</button></>}
      <MutationStatus action={create} success="訂單已建立，正在保存恢復付款所需的訂單紀錄。" />
    </> : order.loading ? <Loading /> : order.error ? <ErrorState error={order.error} retry={order.reload} /> : order.data && <>
      <div className="selection-summary"><strong>{paid ? "已恢復付款完成紀錄" : "已恢復您的購點訂單"}</strong><span>訂單：{order.data.id}</span><span>{order.data.points} 點 · TWD {(Number(order.data.amount_minor) / 100).toLocaleString()}</span><span>後端核對結果：<Status value={order.data.status} /></span></div>
      <Notice>{paid ? "付款結果以此訂單的後端狀態為準，重新整理或返回此頁不會重新付款或重複入點。" : "只有目前操作者有權讀取的訂單可恢復；付款前先保存訂單草稿，返回後重新向後端核對。"}</Notice>
      <div className="actions"><button type="button" className="button button-secondary" onClick={order.reload}>重新核對訂單狀態</button>{session?.development && order.data.status === "unpaid" && <button className="button" disabled={!draft.ready || draft.dirty || draft.saving || settle.pending || !!settle.result} onClick={async () => { if (await settle.mutate(`/development/payments/${order.data?.id}/settle`)) { order.reload(); refreshWallet(); } }}>執行本機 sandbox 支付驗證</button>}</div>
      <MutationStatus action={settle} success="Sandbox 付款已完成；返回頁面將恢復同一訂單，請核對後端結果。" />
      {paid && <button className="button button-secondary" disabled={!draft.ready || draft.saving} onClick={async () => { if (await draft.clear()) { setReview(false); create.clear(); settle.clear(); } }}>完成此訂單並開始新的購點草稿</button>}
    </>}
  </div></Card>;
}
