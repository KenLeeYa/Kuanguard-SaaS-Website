"use client";
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) { return <main id="main-content" className="state-box"><strong>此頁面暫時無法載入</strong><p>請重新整理後再試，已由後端儲存的紀錄不會因此刪除。</p><button className="button" onClick={reset}>重新載入</button></main>; }
