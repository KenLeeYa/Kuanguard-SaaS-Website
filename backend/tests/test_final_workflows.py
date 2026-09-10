from datetime import timedelta
from pathlib import Path

from kuanguard import models as m
from kuanguard.db import all_rows, one
from kuanguard.seed import fixed
from test_platform import make_campaign, post

ROOT = Path(__file__).resolve().parents[2]


def prepare_owner_batch(owner):
    batch = post(owner, f"/internal/projects/{fixed('project-a')}/batches", {
        "service_code": "VA", "title": "CSV precedence fixture", "planned_assets": ["192.0.2.10", "192.0.2.20"]}).json()
    result = post(owner, f"/internal/batches/{batch['id']}/schedule", {
        "start_at": (m.now()+timedelta(days=8)).isoformat(), "end_at": (m.now()+timedelta(days=8,hours=1)).isoformat(),
        "engineer_id": fixed("owner-a"), "reviewer_id": fixed("owner-a"), "equipment": "qa", "reason": "authorized single actor"})
    assert result.status_code == 200, result.text
    return batch


def commit_source(owner, batch, filename, content):
    preview = post(owner, "/internal/imports/preview", {"batch_id": batch["id"], "filename": filename, "content": content})
    assert preview.status_code == 200 and not preview.json()["errors"], preview.text
    assert post(owner, f"/internal/imports/{preview.json()['id']}/commit").status_code == 200


def test_committed_sources_keep_csv_precedence_and_real_comparison(platform):
    owner = platform["login"]("owner-a")
    batch = prepare_owner_batch(owner)
    commit_source(owner, batch, "a.nessus", (ROOT / "samples/reports/inputs/va_initial.nessus").read_text(encoding="utf-8"))
    commit_source(owner, batch, "a.csv", "Plugin ID,Risk,Host,Port,Protocol,Name,Description,Solution\n100001,Low,192.0.2.10,443,tcp,Reviewed title,Reviewed description,Reviewed fix\n")
    assert post(owner, f"/internal/batches/{batch['id']}/review", {"decision":"approved", "note":"CSV is authoritative"}).status_code == 200
    job = post(owner, "/internal/report-jobs", {"batch_id":batch["id"]})
    assert job.status_code == 200, job.text
    snapshot = owner.get(f"/internal/report-jobs/{job.json()['id']}").json()["snapshot"]
    assert snapshot["statistics"]["source_record_count"] == 1
    assert snapshot["statistics"]["severity_counts"] == {"Critical":0, "High":0, "Medium":0, "Low":1}
    assert snapshot["statistics"]["completed_asset_count"] == 2
    assert len(snapshot["sources"]) == 2 and len(snapshot["source_comparison"]) == 2
    assert any(row["only_in_source"] == 2 for row in snapshot["source_comparison"])
    assert any(row["changed_occurrences"] for row in snapshot["source_comparison"])
    with platform["engine"].connect() as conn:
        assert len(all_rows(conn, m.findings, fixed("tenant-a"), m.findings.c.batch_id == batch["id"])) == 3
    policy = post(owner, f"/internal/projects/{fixed('project-a')}/review-policy", {
        "requires_independent_review":True, "reason":"Customer contract now requires independent approval"})
    assert policy.status_code == 200, policy.text
    assert post(owner, "/internal/report-jobs", {"batch_id":batch["id"]}).status_code == 403
    assert post(owner, "/internal/publications", {"report_job_id":job.json()["id"],"note":"must re-review"}).status_code == 403


def test_reviewed_events_drive_single_remediation_reservation(platform):
    customer = platform["login"]()
    campaign = make_campaign(customer, "accepted")
    message = campaign["messages"][0]
    with platform["engine"].connect() as conn:
        route = one(conn, m.jobs, None, m.jobs.c.resource_id == message["id"], m.jobs.c.kind == "tracking_lookup")
    for _ in range(2):
        assert post(customer, f"/sim/{route['id']}/events", {"event_type":"clicked_candidate"}).status_code == 200
    current = customer.get(f"/customer/campaigns/{campaign['id']}").json()
    assert current["metrics"]["clicked_candidate"] == 1
    assert post(customer, f"/customer/campaigns/{campaign['id']}/remediation").json()["items"] == []
    event = next(row for row in current["events"] if row["event_type"] == "clicked_candidate")
    path = f"/customer/campaigns/{campaign['id']}/events/{event['id']}/review"
    payload = {"classification":"confirmed_human", "reason":"Fixture participant separately confirmed the deliberate action"}
    assert post(platform["login"]("customer-b"), path, payload).status_code == 404
    assert post(platform["login"]("learner-a"), path, payload).status_code == 403
    assert post(customer, path, payload).status_code == 200
    for _ in range(2):
        assigned = post(customer, f"/customer/campaigns/{campaign['id']}/remediation")
        assert assigned.status_code == 200 and len(assigned.json()["items"]) == 1
    assert customer.get("/customer/wallet").json()["reserved"] == 10
    assert customer.get(f"/customer/campaigns/{campaign['id']}").json()["metrics"]["confirmed_human_interaction"] == 1


def test_correction_uses_latest_committed_csv_and_preserves_old_snapshot(platform):
    owner = platform["login"]("owner-a")
    batch = prepare_owner_batch(owner)
    csv = "Plugin ID,Risk,Host,Port,Protocol,Name,Description,Solution\n100001,{severity},192.0.2.10,443,tcp,Title,Description,Fix\n"
    commit_source(owner,batch,"initial.csv",csv.format(severity="High"))
    assert post(owner,f"/internal/batches/{batch['id']}/review",{"decision":"approved","note":"Initial source approved"}).status_code==200
    initial=post(owner,"/internal/report-jobs",{"batch_id":batch["id"]}).json()
    assert post(owner,f"/internal/batches/{batch['id']}/reopen",{"text":"Correct source severity with recorded justification"}).status_code==200
    commit_source(owner,batch,"corrected.csv",csv.format(severity="Low"))
    assert post(owner,f"/internal/batches/{batch['id']}/review",{"decision":"approved","note":"Corrected source approved"}).status_code==200
    corrected=post(owner,"/internal/report-jobs",{"batch_id":batch["id"]}).json()
    old=owner.get(f"/internal/report-jobs/{initial['id']}").json()["snapshot"]
    current=owner.get(f"/internal/report-jobs/{corrected['id']}").json()["snapshot"]
    assert old["findings"][0]["severity"]=="High"
    assert current["findings"][0]["severity"]=="Low"
    assert len(current["source_comparison"])==2 and current["report_version"]=="2"


def test_unknown_delivery_requires_finance_evidence_and_is_not_resent(platform):
    customer = platform["login"]()
    campaign = make_campaign(customer, "unknown")
    finance = platform["login"]("finance-a")
    message = finance.get("/internal/phishing/messages").json()["items"][0]
    assert message["campaign_id"] == campaign["id"]
    body = {"outcome":"rejected", "provider_reference":"synthetic-provider-check", "occurred_at":m.now().isoformat(),
            "reason":"Provider audit proved this message was never accepted"}
    path = f"/internal/phishing/messages/{message['id']}/reconcile"
    assert post(customer, path, body).status_code == 403
    first = post(finance, path, body, key="reconciliation-1")
    assert first.status_code == 200 and first.json()["status"] == "rejected", first.text
    assert post(finance, path, body, key="reconciliation-1").status_code == 200
    assert post(finance, path, body).status_code == 409
    assert customer.get("/customer/wallet").json()["reserved"] == 0
    assert customer.get("/customer/wallet").json()["consumed"] == 0


def test_login_destinations_match_verified_roles_and_admin_host():
    from kuanguard.api import login_destination
    assert login_destination({"portfolio_owner","pm"}, "admin.kuanguard.com") == "/portfolio"
    assert login_destination({"reviewer"}, "localhost") == "/admin/overview"
    assert login_destination({"learner"}, "app.kuanguard.com") == "/learn/courses"
    assert login_destination({"learner","customer_contact"}, "app.kuanguard.com") == "/dashboard"


def test_multiple_nessus_sources_without_csv_preserve_all_completed_asset_risks(platform):
    owner = platform["login"]("owner-a")
    batch = prepare_owner_batch(owner)
    for name,host,severity,risk in [("a","192.0.2.10",4,"Critical"),("b","192.0.2.20",1,"Low")]:
        source = f'<NessusClientData_v2><Report name="synthetic"><ReportHost name="{host}"><HostProperties><tag name="HOST_END">2026-09-10T01:00:00Z</tag></HostProperties><ReportItem pluginID="1001" pluginName="Synthetic" port="443" protocol="tcp" severity="{severity}"><risk_factor>{risk}</risk_factor><description>Fixture</description><solution>Review</solution></ReportItem></ReportHost></Report></NessusClientData_v2>'
        commit_source(owner,batch,name+".nessus",source)
    assert post(owner,f"/internal/batches/{batch['id']}/review",{"decision":"approved","note":"Both source assets covered"}).status_code==200
    job=post(owner,"/internal/report-jobs",{"batch_id":batch["id"]}).json()
    snapshot=owner.get(f"/internal/report-jobs/{job['id']}").json()["snapshot"]
    assert snapshot["statistics"]["source_record_count"]==2
    assert snapshot["statistics"]["severity_counts"]["Critical"]==1
    assert snapshot["statistics"]["severity_counts"]["Low"]==1
    assert all(row["risk_count"]==1 for row in snapshot["statistics"]["assets"] if row["status"]=="completed")
