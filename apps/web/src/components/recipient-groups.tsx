"use client";

import { useRef, useState } from "react";
import { dateTime, items, useDirtyForm, useMutation, useResource } from "@/lib/api";
import { Card, DataTable, ErrorState, Loading, MutationStatus, Notice, PageHeading } from "./ui";

export function RecipientGroups() {
  const action = useMutation();
  const [page, setPage] = useState(1);
  const groups = useResource(`/customer/recipient-groups?page=${page}&page_size=20`);
  const [csv, setCsv] = useState("");
  const [name, setName] = useState("");
  const [workbook, setWorkbook] = useState<{ filename: string; content_base64: string } | null>(null);
  const [fileError, setFileError] = useState("");
  const [reading, setReading] = useState(false);
  const selectedFile = useRef(0);
  useDirtyForm(!!(csv || workbook) && !action.result);
  const errorLabels: Record<string, string> = { invalid_email: "Email 格式無效", duplicate_email: "重複 Email", field_too_long: "姓名或部門過長" };
  return <>
    <PageHeading title="受測群組" description="受測名單與平台登入帳戶分開。名單匯入不會建立管理者權限。" />
    <div className="section-stack">
      <Card title="匯入授權名單 CSV／Excel">
        <form className="form-stack" onSubmit={async e => {
          e.preventDefault();
          const result = await action.mutate(workbook ? "/customer/recipient-imports/xlsx" : "/customer/recipient-imports", workbook ? { name, ...workbook } : { name, csv });
          if (result?.valid_count) groups.reload();
        }}>
          <label>群組名稱<input value={name} maxLength={120} onChange={e => { setName(e.target.value); action.clear(); }} required placeholder="例如：資訊部年度演練" /></label>
          <label>選擇已授權名單<input type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={action.pending} onChange={async e => {
            const generation = ++selectedFile.current;
            const file = e.target.files?.[0];
            setWorkbook(null); setCsv(""); setFileError(""); action.clear();
            if (!file) { setReading(false); return; }
            if (!/\.(csv|xlsx)$/i.test(file.name) || file.size > 2_000_000) { setReading(false); setFileError("請選擇 2 MB 以下的 .csv 或 .xlsx 檔案。"); return; }
            setReading(true);
            try {
              if (/\.xlsx$/i.test(file.name)) {
                const bytes = new Uint8Array(await file.arrayBuffer());
                let binary = "";
                for (let offset = 0; offset < bytes.length; offset += 32768) binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
                if (selectedFile.current === generation) setWorkbook({ filename: file.name.replace(/\.xlsx$/i, ".xlsx"), content_base64: btoa(binary) });
              } else {
                const text = await file.text();
                if (selectedFile.current === generation) setCsv(text);
              }
            } catch { if (selectedFile.current === generation) setFileError("無法讀取此檔案，請重新選擇或貼上 CSV 文字。"); }
            finally { if (selectedFile.current === generation) setReading(false); }
          }} /></label>
          {reading && <p role="status">正在讀取名單檔案…</p>}
          {workbook ? <Notice>已選擇 Excel：{workbook.filename}。後端將檢查單工作表、欄位與有效資料；公式、巨集及外部連結不予接受。</Notice> : <label>CSV 名單內容<textarea rows={6} value={csv} required maxLength={2_000_000} disabled={reading || action.pending} onChange={e => { setCsv(e.target.value); setFileError(""); action.clear(); }} placeholder={"email,department,name\nlearner@example.invalid,資訊部,示範學員"} /></label>}
          <p className="form-help">欄位需包含 email,department,name；上限 10,000 筆與 2 MB。XLSX 僅限一張純資料工作表。請僅提供已獲授權名單，勿含密碼與憑證欄位。</p>
          {fileError && <Notice tone="danger">{fileError}</Notice>}
          <button className="button" disabled={reading || action.pending || !!fileError || !!action.result || (!csv && !workbook)}>驗證並建立受測群組</button>
          <MutationStatus action={{ ...action, result: action.result?.valid_count ? action.result : null }} success="有效受測名單已建立；無效與重複列未納入。" />
          {action.result && <><Notice tone={action.result.valid_count ? "info" : "danger"}>有效名單：{action.result.valid_count} 筆；重複或無效：{items(action.result.errors).length} 列。</Notice>{items(action.result.errors).length > 0 && <DataTable rows={items(action.result.errors)} title="名單驗證結果" columns={[{ key: "row", title: "檔案列號" }, { key: "code", title: "檢查結果", render: r => errorLabels[r.code] || r.code }]} />}</>}
        </form>
      </Card>
      <Card title="已建立群組">{groups.loading ? <Loading /> : groups.error ? <ErrorState error={groups.error} retry={groups.reload} /> : <DataTable rows={items(groups.data)} page={page} total={groups.data?.total} onPage={setPage} title="受測群組" columns={[{ key: "name", title: "群組" }, { key: "recipient_count", title: "有效受測者" }, { key: "created_at", title: "建立時間", render: r => dateTime(r.created_at) }]} />}</Card>
    </div>
  </>;
}
