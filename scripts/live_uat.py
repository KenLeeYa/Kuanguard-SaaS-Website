"""Additive loopback-only synthetic UAT. Receipts allow resuming without replaying completed work."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from kuanguard import models as m  # noqa: E402
from kuanguard.seed import fixed  # noqa: E402
from kuanguard.worker import process_once  # noqa: E402

STATE_PATH = ROOT / ".local/live-uat-state.json"
state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {
    "run_id":str(uuid4()), "started_at":datetime.now(timezone.utc).isoformat(), "completed":{}, "reports":[]}


def save():
    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2),encoding="utf-8")


def login(profile):
    client=httpx.Client(base_url="http://127.0.0.1:8180", timeout=20, headers={"origin":"http://127.0.0.1:3180"})
    response=client.post("/auth/dev/login",json={"profile_key":profile})
    response.raise_for_status()
    client.headers["x-csrf-token"]=response.json()["csrf_token"]
    return client


def post(client,label,path,body=None):
    if label in state["completed"]:
        return state["completed"][label]
    response=client.post(path,json=body or {},headers={"idempotency-key":state["run_id"]+":"+label})
    if response.status_code!=200:
        raise RuntimeError(f"{label}: HTTP {response.status_code}: {response.text[:400]}")
    state["completed"][label]=response.json()
    save()
    return response.json()


def wait_report(owner, job_id):
    for _ in range(50):
        current=owner.get(f"/internal/report-jobs/{job_id}").json()
        if current["status"]=="completed":
            return current
        if current["status"]=="failed":
            raise RuntimeError("Report generation failed: "+str(current.get("error")))
        process_once()
    raise RuntimeError("Report did not complete within bounded worker drain")


def main():
    if "--run" not in sys.argv:
        raise SystemExit("Use --run to add synthetic fixtures to the existing loopback development runtime")
    owner,customer,learner,other=login("owner-a"),login("customer-a"),login("learner-a"),login("customer-b")
    now=datetime.fromisoformat(state["started_at"])
    services=[("VA","va_initial.nessus",["192.0.2.10","192.0.2.20","192.0.2.30"]),
              ("WVA","wva_initial.xml",["https://app.example.test","https://portal.example.test"]),
              ("SHC","shc_initial.json",["192.0.2.10","192.0.2.20"]),
              ("PT","pt_initial.json",["https://app.example.test","https://portal.example.test"]),
              ("SOURCE","source_initial.sarif",["src/demo.py","src/excluded.py"])]
    for index,(service,filename,assets) in enumerate(services):
        post(owner,service+"-grant","/internal/entitlements/grants",{"project_id":fixed("project-a"),"service_code":service,"quantity":1,"reason":"本機整合驗收專用合成有限額度，不代表實際採購。"})
        batch=post(owner,service+"-batch",f"/internal/projects/{fixed('project-a')}/batches",{"service_code":service,"title":f"整合驗收合成 {service}","planned_assets":assets})
        start=now+timedelta(days=30,hours=index*3)
        post(owner,service+"-schedule",f"/internal/batches/{batch['id']}/schedule",{"start_at":start.isoformat(),"end_at":(start+timedelta(hours=1)).isoformat(),"engineer_id":fixed("owner-a"),"reviewer_id":fixed("owner-a"),"equipment":"synthetic-uat-kit","reason":"合成時段，驗證單一真實 actor 的明示角色"})
        preview=post(owner,service+"-preview","/internal/imports/preview",{"batch_id":batch["id"],"filename":filename,"content":(ROOT/"samples/reports/inputs"/filename).read_text(encoding="utf-8")})
        assert not preview["errors"]
        post(owner,service+"-commit",f"/internal/imports/{preview['id']}/commit")
        post(owner,service+"-review",f"/internal/batches/{batch['id']}/review",{"decision":"approved","note":"逐項確認合成來源、範圍與統計；本機測試核定。"})
        job=post(owner,service+"-report","/internal/report-jobs",{"batch_id":batch["id"]})
        ready=wait_report(owner,job["id"])
        publication=post(owner,service+"-publish","/internal/publications",{"report_job_id":job["id"],"note":"合成驗收交付，非正式客戶報告。"})
        hashes={}
        assert other.get(f"/customer/reports/{publication['id']}/download/pdf").status_code==404
        for format in ["docx","pdf","pptx","xlsx","csv"]:
            artifact=customer.get(f"/customer/reports/{publication['id']}/download/{format}")
            assert artifact.status_code==200 and "no-store" in artifact.headers["cache-control"]
            hashes[format]=hashlib.sha256(artifact.content).hexdigest()
        post(customer,service+"-acceptance",f"/customer/projects/{fixed('project-a')}/acceptance",{"batch_id":batch["id"],"decision":"accepted","comment":"本機合成 UAT 單批交付確認。"})
        state["reports"]=[row for row in state["reports"] if row["service"]!=service]+[{"service":service,"publication_id":publication["id"],"snapshot_hash":ready["snapshot"]["snapshot_hash"],"artifact_sha256":hashes}]
        save()
        print(service+" import/review/5-format publication/customer download passed",flush=True)
    order=post(customer,"sandbox-order","/customer/wallet/orders",{"points":100})
    post(customer,"sandbox-payment",f"/development/payments/{order['id']}/settle")
    group=post(customer,"recipients","/customer/recipient-imports",{"name":"整合驗收合成受測名單","csv":"email,department,name\nlearner-a@example.invalid,資訊部,合成學員\n"})
    campaign=post(customer,"campaign","/customer/campaigns",{"name":"整合驗收教育活動（未實寄）","group_id":group["id"],"scheduled_at":(now+timedelta(hours=1)).isoformat(),"remediation_course_id":fixed("course")})
    post(customer,"campaign-schedule",f"/customer/campaigns/{campaign['id']}/schedule",{"confirmed":True})
    post(customer,"campaign-simulation",f"/development/campaigns/{campaign['id']}/dispatch",{"outcome":"accepted"})
    enrollment=post(customer,"enrollment","/customer/training/enrollments",{"course_id":fixed("course"),"learner_id":fixed("learner-a"),"cohort":"uat-"+state["run_id"][:8]})
    post(learner,"start-learning",f"/learner/enrollments/{enrollment['id']}/start")
    lessons=learner.get(f"/learner/enrollments/{enrollment['id']}/lessons").json()["items"]
    detail=learner.get(f"/learner/enrollments/{enrollment['id']}").json()
    elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(detail["started_at"])).total_seconds()
    remaining=max(0,sum(row["min_seconds"] for row in lessons)+2-elapsed)
    print(f"Learning server elapsed-time check: waiting {remaining:.0f}s; no timestamp adjustment",flush=True)
    while remaining>0:
        pause=min(remaining,10)
        time.sleep(pause)
        remaining-=pause
    for lesson in lessons:
        post(learner,"progress-"+lesson["id"],f"/learner/enrollments/{enrollment['id']}/progress",{"lesson_id":lesson["id"],"seconds":lesson["min_seconds"]})
    questions=learner.get(f"/learner/enrollments/{enrollment['id']}/questions").json()["items"]
    from kuanguard.catalog import COURSE_QUESTIONS
    correct={prompt:answer for prompt,_,answer,_ in COURSE_QUESTIONS}
    result=post(learner,"assessment","/learner/attempts",{"enrollment_id":enrollment["id"],"answers":[{"question_id":question["id"],"choice":correct[question["prompt"]]} for question in questions]})
    assert result["passed"] and result["certificate_id"]
    certificate=customer.get(f"/public/certificates/{result['certificate_id']}").json()
    assert certificate["valid"] and "email" not in certificate and "learner_name" not in certificate
    latency=[]
    for _ in range(20):
        started=time.perf_counter()
        response=customer.get("/customer/dashboard")
        response.raise_for_status()
        latency.append((time.perf_counter()-started)*1000)
    receipt={"status":"LOCAL_SYNTHETIC_UAT_PASSED","run_id":state["run_id"],"completed_at":m.now().isoformat(),
             "scope":"existing loopback API and PostgreSQL; additive fixtures; no production claims", "reports":state["reports"],
             "campaign_id":campaign["id"],"real_mail_sent":0,"real_money_charged":0,"certificate_id":result["certificate_id"],
             "sample_dashboard_latency_ms":{"n":len(latency),"p50":round(statistics.median(latency),2),"p95":round(sorted(latency)[18],2)},
             "browser_visual_verified":False}
    target=ROOT/"docs/evidence/live-uat.json"
    target.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False),flush=True)
    for client in [owner,customer,learner,other]:
        client.close()


if __name__=="__main__":
    main()
