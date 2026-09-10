"use client";

import { dateOnly, dateTime, items, useResource } from "@/lib/api";
import { PurchaseForm } from "./draft-forms";
import { Card, DataTable, ErrorState, Loading, Metric, Notice, PageHeading } from "./ui";

export function WalletPage() {
  const wallet = useResource("/customer/wallet");
  if (wallet.loading) return <Loading />;
  if (wallet.error) return <ErrorState error={wallet.error} retry={wallet.reload} />;
  const data = wallet.data!;
  return <><PageHeading title="企業點數錢包" description="演練與教育共用點數；服務席次、付費、贈送與用途限制分開記帳。" /><div className="metrics"><Metric label="可用點數" value={data.available} suffix="點" detail="已扣除有效預留" /><Metric label="已預留" value={data.reserved} suffix="點" detail="排程與未啟動派課" /><Metric label="已使用" value={data.consumed} suffix="點" detail="依帳本消費紀錄" /><Metric label="即將到期" value={typeof data.expiring === "number" ? data.expiring : items(data.expiring).reduce((sum, row) => sum + Number(row.available || 0), 0)} suffix="點" detail="依原點數批次有效期限" /></div>{data.sandbox && <Notice>目前使用開發金流與測試費率，沒有實際付款。正式點數價格、效期、退款與發票政策尚待核定。</Notice>}<div className="section-stack">
    <PurchaseForm wallet={data} refreshWallet={wallet.reload} />
    <Card title="點數批次"><DataTable rows={items(data.lots)} columns={[{ key: "source", title: "來源", render: r => r.source || r.source_type || r.kind }, { key: "purpose", title: "用途限制", render: r => r.purpose === "training" ? "限教育訓練" : r.purpose === "phishing" ? "限社交工程" : "依批次適用" }, { key: "quantity", title: "原始點數", render: r => r.quantity ?? r.granted ?? r.points }, { key: "available", title: "可用點數" }, { key: "expires_at", title: "有效期限", render: r => dateOnly(r.expires_at) }]} /></Card>
    <Card title="點數交易紀錄"><DataTable rows={items(data.transactions)} columns={[{ key: "created_at", title: "時間（Asia/Taipei）", render: r => dateTime(r.created_at) }, { key: "kind", title: "交易類型" }, { key: "quantity", title: "點數", render: r => `可用 ${r.available_delta > 0 ? "+" : ""}${r.available_delta ?? 0} / 預留 ${r.reserved_delta > 0 ? "+" : ""}${r.reserved_delta ?? 0} / 使用 ${r.consumed_delta > 0 ? "+" : ""}${r.consumed_delta ?? 0}` }, { key: "purpose", title: "用途" }, { key: "reason", title: "說明" }]} /></Card>
  </div></>;
}
