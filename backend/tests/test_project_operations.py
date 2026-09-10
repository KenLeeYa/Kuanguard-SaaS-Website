import base64
from datetime import datetime, timedelta
from io import BytesIO
import zipfile

from openpyxl import Workbook

from kuanguard import models as m
from kuanguard.db import all_rows, aware
from kuanguard.seed import fixed
from test_platform import post


def test_finite_service_quota_reservation_cancel_and_points_separation(platform):
    owner, customer = platform["login"]("owner-a"), platform["login"]()
    path = f"/internal/projects/{fixed('project-a')}/batches"
    body = {"service_code":"VA", "title":"Finite authorization", "planned_assets":[]}
    first, second = post(owner,path,body), post(owner,path,body)
    assert first.status_code == second.status_code == 200
    assert post(owner,path,body).status_code == 409
    balance = next(row for row in customer.get("/customer/entitlements").json()["items"] if row["service_code"] == "VA")
    assert balance["available"] == 0 and balance["reserved"] == 2
    assert post(owner, f"/internal/batches/{first.json()['id']}/cancel", {"text":"Customer withdrew before execution"}).status_code == 200
    assert post(owner,path,body).status_code == 200
    assert customer.get("/customer/wallet").json()["available"] == 540
    assert post(customer, "/internal/entitlements/grants", {"project_id":fixed("project-a"),"service_code":"VA","quantity":1,"reason":"Unauthorized attempt to increase service quota"}).status_code == 403


def test_online_scope_price_confirmation_keeps_old_scope_and_rejects_stale_version(platform):
    owner, customer = platform["login"]("owner-a"), platform["login"]()
    project_id = fixed("project-a")
    batch_id = fixed("batch-a-VA")
    change = post(customer, f"/customer/projects/{project_id}/changes", {
        "batch_id":batch_id,"kind":"scope","reason":"Add authorized scope", "proposed_assets":["192.0.2.99"]}).json()
    path = f"/internal/changes/{change['id']}"
    offered = post(owner, path+"/offer", {"expected_version":1,"amount_minor":10000,"reason":"Additional asset fee quotation"}).json()
    assert offered["version"] == 2
    newer = post(owner, path+"/offer", {"expected_version":2,"amount_minor":12000,"reason":"Revised additional asset quotation"}).json()
    assert post(owner,path+"/apply", {"expected_version":3}).status_code == 409
    assert post(customer,f"/customer/changes/{change['id']}/confirm", {"version":2,"intent":"accept"}).status_code == 409
    assert post(customer,f"/customer/changes/{change['id']}/confirm", {"version":newer["version"],"intent":"accept"}).status_code == 200
    assert post(owner,path+"/apply", {"expected_version":3}).status_code == 200
    current = customer.get(f"/customer/projects/{project_id}").json()
    assert "192.0.2.99" in next(row for row in current["batches"] if row["id"] == batch_id)["planned_assets"]
    with platform["engine"].connect() as conn:
        assets = all_rows(conn,m.scope_assets,fixed("tenant-a"),m.scope_assets.c.batch_id==batch_id)
        assert {row["version"] for row in assets} == {1,2}
    assert post(owner,path+"/apply", {"expected_version":3}).status_code == 409


def test_schedule_change_keeps_original_time_and_rechecks_conflicts(platform):
    owner, customer = platform["login"]("owner-a"), platform["login"]()
    project_id, batch_id = fixed("project-a"), fixed("batch-a-VA")
    start=m.now()+timedelta(days=6)
    schedule={"start_at":start.isoformat(),"end_at":(start+timedelta(hours=1)).isoformat(), "engineer_id":fixed("owner-a"),
              "reviewer_id":fixed("owner-a"),"equipment":"test-kit","reason":"Authorized fieldwork"}
    assert post(owner,f"/internal/batches/{batch_id}/schedule",schedule).status_code==200
    proposed=start+timedelta(days=1)
    change=post(customer,f"/customer/projects/{project_id}/changes",{"batch_id":batch_id,"kind":"reschedule","reason":"Customer requested new slot","proposed_start":proposed.isoformat()}).json()
    assert post(owner,f"/internal/changes/{change['id']}/offer",{"expected_version":1,"amount_minor":0,"reason":"No extra fee for this change"}).status_code==200
    assert post(customer,f"/customer/changes/{change['id']}/confirm",{"version":2,"intent":"accept"}).status_code==200
    moved={**schedule,"start_at":proposed.isoformat(),"end_at":(proposed+timedelta(hours=1)).isoformat()}
    assert post(owner,f"/internal/batches/{fixed('batch-a-WVA')}/schedule",moved).status_code==200
    assert post(owner,f"/internal/changes/{change['id']}/apply",{"expected_version":2,"schedule":moved}).status_code==409
    batch=owner.get(f"/internal/projects/{project_id}").json()["batches"]
    assert aware(datetime.fromisoformat(next(row for row in batch if row["id"]==batch_id)["original_start_at"]))==start


def workbook_payload(formula=False):
    book=Workbook()
    book.active.append(["email","department","name"])
    book.active.append(["learner-a@example.invalid","資訊部", "=1+1" if formula else "學員A"])
    buffer=BytesIO()
    book.save(buffer)
    return {"name":"XLSX 合成名單", "filename":"roster.xlsx", "content_base64":base64.b64encode(buffer.getvalue()).decode()}


def test_xlsx_valid_import_formula_and_archive_traversal_rejection(platform):
    customer=platform["login"]()
    response=post(customer,"/customer/recipient-imports/xlsx",workbook_payload())
    assert response.status_code==200 and response.json()["valid_count"]==1,response.text
    assert post(customer,"/customer/recipient-imports/xlsx",workbook_payload(True)).status_code==422
    buffer=BytesIO()
    with zipfile.ZipFile(buffer,"w") as archive:
        archive.writestr("../escape.xml","<a/>")
    assert post(customer,"/customer/recipient-imports/xlsx",{**workbook_payload(),"content_base64":base64.b64encode(buffer.getvalue()).decode()}).status_code==422
