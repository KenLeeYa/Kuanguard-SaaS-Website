"use client";

import { ArrowUpRight, LogIn, ClipboardList, Store } from "lucide-react";
import { stallOrder } from "@/lib/product-links";
import { Localized } from "./website-language";

export function StallOrderEntry() {
  return <Localized><section className="commerce-container stallorder-entry" aria-labelledby="stallorder-title">
    <div className="stallorder-brand"><Store size={28} aria-hidden="true" /><span>KUANGUARD / STALLORDER</span></div>
    <div className="stallorder-entry-grid"><div><p className="commerce-eyebrow">專為餐飲門市與攤商打造</p><h2 id="stallorder-title">認識攤點通，<br />找到適合店裡的點餐方式。</h2><p>從線上菜單、QR 點餐到 POS 與廚房出單，前往攤點通官網了解完整功能、費用及導入流程。</p><a className="commerce-button" href={stallOrder.website}>了解攤點通<ArrowUpRight size={18} aria-hidden="true" /></a><small className="stallorder-domain">qidaigo.com · 攤點通官方網站</small></div>
      <div className="stallorder-quick-links"><a href={stallOrder.apply}><ClipboardList size={23} aria-hidden="true" /><span><strong>申請商家開通</strong><small>前往 Google 表單，留下門市需求。</small></span><ArrowUpRight size={18} aria-hidden="true" /></a><a href={stallOrder.login}><LogIn size={23} aria-hidden="true" /><span><strong>商家登入</strong><small>已有帳號，直接進入攤點通。</small></span><ArrowUpRight size={18} aria-hidden="true" /></a><p>這些入口會前往攤點通或 Google 表單；申請與登入由對應服務處理。</p></div></div>
  </section></Localized>;
}
