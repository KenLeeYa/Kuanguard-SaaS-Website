"use client";

import { useState } from "react";
import Link from "./guarded-link";
import { platformEntries } from "@/lib/product-links";
import { Localized, useWebsiteText } from "./website-language";

export function WebsiteContact({ email, title = "聯絡 KUANGUARD" }: { email: string; title?: string }) {
  const [opened, setOpened] = useState(false);
  const text = useWebsiteText();
  return <Localized><div className="commerce-site"><section className="commerce-container commerce-section">
    <h1>{title}</h1><p>告訴我們你的使用情境，一起確認適合的產品與服務。</p>
    <p>聯絡信箱：<a href={`mailto:${email}`}>{email}</a></p>
    <form className="commerce-form" onSubmit={event => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      const body = `${text("公司／組織名稱")}: ${data.get("company")}\n${text("聯絡人")}: ${data.get("name")}\n${text("聯絡 Email")}: ${data.get("email")}\n\n${text("需求說明")}:\n${data.get("message")}`;
      window.location.href = `mailto:${email}?subject=${encodeURIComponent(`KUANGUARD｜${text(title)}`)}&body=${encodeURIComponent(body)}`;
      setOpened(true);
    }}>
      <div className="commerce-form-grid">
        <label>公司／組織名稱<input name="company" autoComplete="organization" maxLength={160} required /></label>
        <label>聯絡人<input name="name" autoComplete="name" maxLength={120} required /></label>
        <label>聯絡 Email<input name="email" type="email" autoComplete="email" maxLength={254} required /></label>
      </div>
      <label>需求說明<textarea name="message" rows={5} maxLength={1500} required /></label>
      <p>按下按鈕後，請在你的郵件程式確認內容並寄出。本站不會儲存表單內容；請勿填入密碼或敏感資料。<Link href="/privacy">隱私權政策</Link></p>
      <button className="commerce-button" type="submit">開啟郵件程式</button>
      {opened && <p role="status">請在郵件程式完成寄送；若沒有開啟，請直接寄信至 {email}。此頁尚未替你寄出郵件。</p>}
    </form>
  </section></div></Localized>;
}

export function WebsiteEntry({ email, courses = false, product }: { email: string; courses?: boolean; product?: string }) {
  const entries = product ? platformEntries.filter(entry => entry.id === product) : platformEntries;
  return <Localized><div className="commerce-site"><section className="commerce-container commerce-section">
    <h1>{courses ? "課程目錄準備中" : product ? entries[0]?.name : "選擇你的系統"}</h1>
    <p>{courses ? "課程將於教材與授權確認後開放。" : "各系統使用各自的帳號與登入頁面，請選擇你正在使用的產品。"}</p>
    {!courses && <div className="website-entry-grid">{entries.map(entry => <article className="website-entry-card" key={entry.id}><h2>{entry.name}</h2><p>{entry.description}</p>{entry.login ? <a className="commerce-button" href={entry.login}>商家登入</a> : <span className="kg-platform-status">平台尚未開放</span>}<Link href={entry.details}>了解產品與服務</Link></article>)}</div>}
    <p><a href={`mailto:${email}`}>聯絡 KUANGUARD</a></p><Link href="/products">探索產品與平台</Link>
  </section></div></Localized>;
}
