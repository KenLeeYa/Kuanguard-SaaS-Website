from datetime import timedelta
from pathlib import Path

import pytest

from kuanguard import models as m
from kuanguard.seed import fixed
from kuanguard.worker import process_once
from test_platform import post

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("service,filename,assets", [
    ("VA", "va_initial.nessus", ["192.0.2.10", "192.0.2.20", "192.0.2.30"]),
    ("WVA", "wva_initial.xml", ["https://app.example.test", "https://portal.example.test"]),
    ("SHC", "shc_initial.json", ["192.0.2.10", "192.0.2.20"]),
    ("PT", "pt_initial.json", ["https://app.example.test", "https://portal.example.test"]),
    ("SOURCE", "source_initial.sarif", ["src/demo.py", "src/excluded.py"]),
])
def test_five_engineer_services_actual_import_to_customer_bundle(platform, service, filename, assets):
    owner, customer, other = platform["login"]("owner-a"), platform["login"](), platform["login"]("customer-b")
    created = post(owner, f"/internal/projects/{fixed('project-a')}/batches", {"service_code": service, "title": f"UAT {service}", "planned_assets": assets})
    assert created.status_code == 200, created.text
    batch = created.json()
    schedule = post(owner, f"/internal/batches/{batch['id']}/schedule", {"start_at": (m.now()+timedelta(days=5)).isoformat(),
        "end_at": (m.now()+timedelta(days=5,hours=1)).isoformat(), "engineer_id": fixed("owner-a"), "reviewer_id": fixed("owner-a"), "equipment": "uat-kit", "reason": "single actor authorized fixture"})
    assert schedule.status_code == 200, schedule.text
    body = {"batch_id": batch["id"], "filename": filename, "content": (ROOT / "samples/reports/inputs" / filename).read_text(encoding="utf-8")}
    preview = post(owner, "/internal/imports/preview", body)
    assert preview.status_code == 200 and not preview.json()["errors"], preview.text
    import_id = preview.json()["id"]
    assert post(owner, f"/internal/imports/{import_id}/commit").status_code == 200
    assert customer.get("/customer/findings").json()["total"] == 0
    assert post(owner, f"/internal/batches/{batch['id']}/review", {"decision": "approved", "note": "逐項檢查合成資料及覆蓋範圍"}).status_code == 200
    job = post(owner, "/internal/report-jobs", {"batch_id": batch["id"]})
    assert job.status_code == 200, job.text
    processed = process_once()
    assert processed["status"] == "processed", processed
    details = owner.get(f"/internal/report-jobs/{job.json()['id']}")
    assert details.status_code == 200 and details.json()["status"] == "completed", details.text
    snapshot = details.json()["snapshot"]
    assert snapshot["service_code"] == service
    if service == "SHC":
        assert snapshot["statistics"]["shc"]["check_counts"]["insufficient"] == 1
    if service == "SOURCE":
        assert snapshot["metadata"]["excluded_paths"]
    publication = post(owner, "/internal/publications", {"report_job_id": job.json()["id"], "note": "合成示範報告覆核完成"})
    assert publication.status_code == 200, publication.text
    publication_id = publication.json()["id"]
    assert other.get(f"/customer/reports/{publication_id}/download/pdf").status_code == 404
    for format in ["docx", "pdf", "pptx", "xlsx", "csv"]:
        artifact = customer.get(f"/customer/reports/{publication_id}/download/{format}")
        assert artifact.status_code == 200 and len(artifact.content) > 100
        assert "no-store" in artifact.headers["cache-control"]
    published = customer.get("/customer/findings?page_size=100").json()["items"]
    dashboard = customer.get("/customer/dashboard").json()
    for level, count in snapshot["statistics"]["severity_counts"].items():
        assert dashboard["risks"][level] == count
    assert all("review_note" not in item and "reviewer_id" not in item and "engineer_id" not in item for item in dashboard["upcoming"])
    assert published and all(item["id"] for item in published)
    assert all("evidence" not in item and "details" not in item for item in published)
    first = published[0]
    assert post(customer, f"/customer/findings/{first['id']}/replies", {"text": "已依建議處理，請確認複測。"}).status_code == 200
    retest_request = post(customer, "/customer/retest-requests", {"batch_id": batch["id"], "finding_ids": [first["id"]], "reason": "申請授權範圍複測"})
    assert retest_request.status_code == 200
    assert post(customer, f"/customer/projects/{fixed('project-a')}/acceptance", {"batch_id": batch["id"], "decision": "accepted", "comment": "此批次交付確認"}).status_code == 200
    assert customer.get(f"/customer/projects/{fixed('project-a')}").json()["status"] == "active"
    if service == "VA":
        from test_final_workflows import commit_source
        original_pdf = customer.get(f"/customer/reports/{publication_id}/download/pdf").content
        retest = post(owner, f"/internal/retest-requests/{retest_request.json()['id']}/approve").json()
        commit_source(owner, retest, "va_retest.nessus", (ROOT / "samples/reports/inputs/va_retest.nessus").read_text(encoding="utf-8"))
        original = next(row for row in snapshot["findings"] if row["severity"] == "High")
        proof = post(owner, f"/internal/batches/{retest['id']}/retest-verifications", {"finding_id":original["id"],
            "method":original["method"], "scope_confirmed":True, "evidence":"原資產、連接埠及檢核方法已個別驗證，合成修復證據 VA-001。"})
        assert proof.status_code == 200, proof.text
        assert post(owner, f"/internal/batches/{retest['id']}/review", {"decision":"approved","note":"覆蓋與個別驗證完成"}).status_code == 200
        retest_job = post(owner, "/internal/report-jobs", {"batch_id":retest["id"]}).json()
        assert process_once()["status"] == "processed"
        result = owner.get(f"/internal/report-jobs/{retest_job['id']}").json()["snapshot"]
        assert next(row for row in result["retest"] if row["source_id"] == "100001")["status"] == "verified_remediated"
        assert next(row for row in result["retest"] if row["source_id"] == "100002")["status"] == "persistent"
        assert post(owner,"/internal/publications",{"report_job_id":retest_job["id"],"note":"合成複測交付"}).status_code == 200
        assert post(owner,f"/internal/batches/{batch['id']}/reopen",{"text":"原交付統計更正，保留原版"}).status_code == 200
        commit_source(owner, batch, "correction.csv", "Plugin ID,Risk,Host,Port,Protocol,Name,Description,Solution\n100001,Low,192.0.2.10,443,tcp,Corrected,Reviewed,Update\n")
        assert post(owner,f"/internal/batches/{batch['id']}/review",{"decision":"approved","note":"更正來源已人工確認"}).status_code == 200
        correction = post(owner,"/internal/report-jobs",{"batch_id":batch["id"]}).json()
        assert process_once()["status"] == "processed"
        revised = post(owner,"/internal/publications",{"report_job_id":correction["id"],"note":"更正版本，原交付仍可追溯"})
        assert revised.status_code == 200 and revised.json()["supersedes_id"] == publication_id, revised.text
        assert customer.get(f"/customer/reports/{publication_id}/download/pdf").content == original_pdf
        quota = next(row for row in customer.get("/customer/entitlements").json()["items"] if row["service_code"]=="VA")
        assert quota["consumed"] == 2 and quota["reserved"] == 0
