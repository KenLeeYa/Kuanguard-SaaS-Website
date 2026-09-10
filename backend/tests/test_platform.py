from datetime import timedelta
import hmac
import json
import time
from uuid import uuid4

import pytest
from fastapi import HTTPException

from kuanguard import models as m, wallet
from kuanguard.db import all_rows, change, one
from kuanguard.seed import fixed


def post(client, path, payload=None, key=None):
    return client.post(path, json=payload if payload is not None else {}, headers={"idempotency-key": key or str(uuid4())})


def test_tenant_roles_csrf_and_forced_customer_uploads(platform):
    customer = platform["login"]()
    other = platform["login"]("customer-b")
    learner = platform["login"]("learner-a")
    finance = platform["login"]("finance-a")
    project_b = other.get("/customer/projects").json()["items"][0]["id"]
    assert customer.get(f"/customer/projects/{project_b}").status_code == 404
    assert learner.get("/customer/wallet").status_code == 403
    assert learner.get("/customer/reports").status_code == 403
    assert finance.get("/internal/findings").status_code == 403
    for path in ["/internal/imports/preview", "/internal/evidence/sign", "/internal/evidence/finalize"]:
        payload = {"batch_id": fixed("batch-a-VA"), "filename": "a.csv", "content": "Risk,Host,Name,Plugin ID\nHigh,192.0.2.10,Demo,1"}
        response = post(customer, path, payload)
        assert response.status_code in {403, 404}, response.text
    assert post(customer, "/customer/wallet/orders", {"points": 100, "tenant_id": fixed("tenant-b")}).status_code == 422
    assert customer.post("/customer/wallet/orders", json={"points": 100}, headers={"x-csrf-token": "forged", "idempotency-key": str(uuid4())}).status_code == 403
    assert customer.post("/customer/wallet/orders", json={"points": 100}, headers={"origin": "https://evil.invalid", "idempotency-key": str(uuid4())}).status_code == 403


def test_wallet_purchase_idempotency_and_partial_refund(platform):
    customer = platform["login"]()
    key = str(uuid4())
    first = post(customer, "/customer/wallet/orders", {"points": 100}, key).json()
    second = post(customer, "/customer/wallet/orders", {"points": 100}, key).json()
    assert first["id"] == second["id"]
    assert post(customer, "/customer/wallet/orders", {"points": 500}, key).status_code == 409
    for _ in range(2):
        assert post(customer, f"/development/payments/{first['id']}/settle").status_code == 200
    assert customer.get("/customer/wallet").json()["available"] == 640
    finance = platform["login"]("finance-a")
    result = post(finance, "/internal/billing/refunds", {"order_id": first["id"], "amount_minor": 2500, "reason": "sandbox partial"})
    assert result.status_code == 200 and result.json()["status"] == "completed_sandbox"
    assert customer.get("/customer/wallet").json()["available"] == 615
    assert finance.get("/internal/billing/reconciliation").json()["status"] == "matched"


def signed_event(client, event, timestamp=None, signature=None):
    body = json.dumps(event, separators=(",", ":")).encode()
    timestamp = str(timestamp or int(time.time()))
    actual = hmac.new(b"local-test-webhook-secret-not-production", timestamp.encode()+b"."+body, "sha256").hexdigest()
    return client.post("/webhooks/payments/sandbox", content=body, headers={"content-type": "application/json", "x-payment-timestamp": timestamp, "x-payment-signature": signature or actual})


def test_payment_signature_product_amount_order_and_replay(platform):
    client = platform["login"]()
    order = post(client, "/customer/wallet/orders", {"points": 100}).json()
    base = {"event_id": "event-1", "order_id": order["id"], "merchant": "kuanguard-sandbox", "amount_minor": 10000,
            "currency": "TWD", "status": "paid", "provider_ref": "sandbox-ref-1", "product_id": "kuanguard"}
    assert signed_event(client, base, signature="forged").status_code == 401
    assert signed_event(client, base, timestamp=int(time.time())-600).status_code == 401
    assert signed_event(client, {**base, "amount_minor": 1}).status_code == 400
    assert signed_event(client, {**base, "merchant": "qidaigo"}).status_code == 400
    assert signed_event(client, {**base, "product_id": "qidaigo"}).status_code == 422
    assert signed_event(client, {**base, "currency": "USD"}).status_code == 422
    assert signed_event(client, {**base, "status": "refunded"}).status_code == 409
    assert signed_event(client, base).status_code == 200
    assert signed_event(client, base).json()["duplicate"] is True
    assert signed_event(client, {**base, "provider_ref": "changed"}).status_code == 409
    assert signed_event(client, {**base, "event_id": "late-failed", "status": "failed"}).json()["status"] == "ignored_late_failure"
    assert client.get("/customer/wallet").json()["available"] == 640
    assert signed_event(client, {**base, "event_id": "chargeback", "status": "chargeback"}).status_code == 200
    assert client.get("/customer/wallet").json()["frozen"] is True


def test_points_expiry_and_restricted_lots(platform):
    tenant = fixed("tenant-b")
    with platform["engine"].begin() as conn:
        far = m.now()+timedelta(days=400)
        with pytest.raises(HTTPException) as error:
            wallet.reserve(conn, tenant, "phishing", "too-late", 1, far)
        assert error.value.status_code == 409
        reservation = wallet.reserve(conn, tenant, "phishing", "all-paid", 500, m.now()+timedelta(days=1))
        with pytest.raises(HTTPException):
            wallet.reserve(conn, tenant, "phishing", "gift-disallowed", 1, m.now()+timedelta(days=1))
        allocations = all_rows(conn, m.reservation_lots, tenant, m.reservation_lots.c.reservation_id == reservation["id"])
        for allocation in allocations:
            change(conn, m.point_lots, tenant, allocation["lot_id"], expires_at=m.now()-timedelta(seconds=1))
        wallet.release(conn, tenant, reservation["id"], "cancel after expiry")
        assert wallet.summary(conn, tenant)["available"] == 40
        assert all(wallet.balances(conn, tenant, allocation["lot_id"])["available"] == 0 for allocation in allocations)


def make_campaign(client, outcome="unknown"):
    group = post(client, "/customer/recipient-imports", {"name": "演練樣本", "csv": "email,department,name\nlearner-a@example.invalid,資訊部,學員A\ninvalid,資訊部,錯誤列\nlearner-a@example.invalid,資訊部,重複"}).json()
    assert group["valid_count"] == 1 and len(group["errors"]) == 2
    campaign = post(client, "/customer/campaigns", {"name": "授權本機活動", "group_id": group["id"],
                         "scheduled_at": (m.now()+timedelta(minutes=5)).isoformat(), "remediation_course_id": fixed("course")}).json()
    scheduled = post(client, f"/customer/campaigns/{campaign['id']}/schedule", {"confirmed": True})
    assert scheduled.status_code == 200, scheduled.text
    dispatched = post(client, f"/development/campaigns/{campaign['id']}/dispatch", {"outcome": outcome})
    assert dispatched.status_code == 200, dispatched.text
    return dispatched.json()


def test_campaign_unknown_cancel_keeps_reservation_and_no_resend(platform):
    client = platform["login"]()
    campaign = make_campaign(client)
    assert campaign["metrics"]["unknown"] == 1
    assert client.get("/customer/wallet").json()["reserved"] == 1
    assert post(client, f"/development/campaigns/{campaign['id']}/dispatch", {"outcome": "accepted"}).json()["metrics"]["unknown"] == 1
    assert post(client, f"/customer/campaigns/{campaign['id']}/cancel").status_code == 200
    assert client.get("/customer/wallet").json()["reserved"] == 1
    other = platform["login"]("customer-b")
    assert other.get(f"/customer/campaigns/{campaign['id']}").status_code == 404


def test_sim_never_collects_password_or_claims_human(platform):
    client = platform["login"]()
    campaign = make_campaign(client, "accepted")
    message = campaign["messages"][0]
    with platform["engine"].begin() as conn:
        route = one(conn, m.jobs, None, m.jobs.c.resource_id == message["id"], m.jobs.c.kind == "tracking_lookup")
    token = route["id"]
    assert client.get(f"/sim/{token}/education").status_code == 200
    assert post(client, f"/sim/{token}/events", {"event_type": "human_interaction", "password": "must-not-store"}).status_code == 422
    response = post(client, f"/sim/{token}/events", {"event_type": "human_interaction"})
    assert response.json()["classification"] == "unverified_candidate"
    assert client.get(f"/customer/campaigns/{campaign['id']}").json()["metrics"]["confirmed_human_interaction"] == 0
    assert client.get("/customer/wallet").json()["consumed"] == 1


def test_lms_charge_once_progress_grading_and_certificate_privacy(platform):
    customer = platform["login"]()
    body = {"course_id": fixed("course"), "learner_id": fixed("learner-a"), "cohort": "2026"}
    assigned = post(customer, "/customer/training/enrollments", body).json()
    again = post(customer, "/customer/training/enrollments", body).json()
    assert assigned["id"] == again["id"]
    assert customer.get("/customer/wallet").json()["reserved"] == 10
    learner = platform["login"]("learner-a")
    other = platform["login"]("learner-a2")
    assert other.get(f"/learner/enrollments/{assigned['id']}").status_code == 404
    assert learner.get(f"/learner/enrollments/{assigned['id']}/video-token").status_code == 409
    for _ in range(2):
        result = post(learner, f"/learner/enrollments/{assigned['id']}/start")
        assert result.status_code == 200, result.text
    assert customer.get("/customer/wallet").json()["consumed"] == 10
    assert learner.get(f"/learner/enrollments/{assigned['id']}/video-token").status_code == 503
    lessons = learner.get(f"/learner/enrollments/{assigned['id']}/lessons").json()["items"]
    assert learner.get(f"/learner/enrollments/{assigned['id']}/questions").status_code == 409
    assert post(learner, f"/learner/enrollments/{assigned['id']}/progress", {"lesson_id": lessons[0]["id"], "seconds": 20}).status_code == 409
    with platform["engine"].begin() as conn:
        change(conn, m.enrollments, fixed("tenant-a"), assigned["id"], started_at=m.now()-timedelta(seconds=70))
    for lesson in lessons:
        assert post(learner, f"/learner/enrollments/{assigned['id']}/progress", {"lesson_id": lesson["id"], "seconds": lesson["min_seconds"]}).status_code == 200
    visible = learner.get(f"/learner/enrollments/{assigned['id']}/questions").json()
    assert "correct_choice" not in json.dumps(visible)
    with platform["engine"].connect() as conn:
        questions = all_rows(conn, m.questions, None, m.questions.c.course_id == fixed("course"))
    answers = [{"question_id": q["id"], "choice": q["correct_choice"]} for q in questions]
    result = post(learner, "/learner/attempts", {"enrollment_id": assigned["id"], "answers": answers})
    assert result.status_code == 200 and result.json()["passed"], result.text
    certificate_id = result.json()["certificate_id"]
    assert other.get(f"/learner/certificates/{certificate_id}").status_code == 404
    verified = customer.get(f"/public/certificates/{certificate_id}").json()
    assert verified["valid"] and "learner_name" not in verified and "email" not in verified


def test_lms_cancel_before_start_releases(platform):
    customer = platform["login"]()
    assigned = post(customer, "/customer/training/enrollments", {"course_id": fixed("course"), "learner_id": fixed("learner-a"), "cohort": "cancel"}).json()
    assert post(customer, f"/customer/training/enrollments/{assigned['id']}/cancel").status_code == 200
    assert customer.get("/customer/wallet").json()["available"] == 540
    learner = platform["login"]("learner-a")
    assert post(learner, f"/learner/enrollments/{assigned['id']}/start").status_code == 409


def test_start_replay_rechecks_current_course_expiry(platform):
    customer, learner = platform["login"](), platform["login"]("learner-a")
    assigned = post(customer, "/customer/training/enrollments", {"course_id": fixed("course"), "learner_id": fixed("learner-a"), "cohort": "expiry-replay"}).json()
    key = str(uuid4())
    assert post(learner, f"/learner/enrollments/{assigned['id']}/start", key=key).status_code == 200
    with platform["engine"].begin() as conn:
        change(conn, m.enrollments, fixed("tenant-a"), assigned["id"], expires_at=m.now()-timedelta(seconds=1))
    assert post(learner, f"/learner/enrollments/{assigned['id']}/start", key=key).status_code == 410


def test_paused_jobs_do_not_exhaust_retry_budget(platform):
    from kuanguard.worker import claim_job
    client = platform["login"]()
    group = post(client, "/customer/recipient-imports", {"name": "pause", "csv": "email,department,name\na@example.invalid,IT,A"}).json()
    campaign = post(client, "/customer/campaigns", {"name": "pause", "group_id": group["id"], "scheduled_at": (m.now()+timedelta(minutes=5)).isoformat()}).json()
    assert post(client, f"/customer/campaigns/{campaign['id']}/schedule", {"confirmed": True}).status_code == 200
    assert post(client, f"/customer/campaigns/{campaign['id']}/pause").status_code == 200
    for _ in range(6):
        assert claim_job() is None
    with platform["engine"].connect() as conn:
        jobs = all_rows(conn, m.jobs, None, m.jobs.c.kind == "sandbox_mail")
        assert jobs[0]["status"] == "paused" and jobs[0]["attempts"] == 0
    assert post(client, f"/customer/campaigns/{campaign['id']}/resume").status_code == 200
    with platform["engine"].connect() as conn:
        jobs = all_rows(conn, m.jobs, None, m.jobs.c.kind == "sandbox_mail")
        assert jobs[0]["status"] == "queued" and jobs[0]["attempts"] == 0


def test_single_owner_schedule_and_contract_independent_policy(platform):
    owner = platform["login"]("owner-a")
    payload = {"start_at": (m.now()+timedelta(days=1)).isoformat(), "end_at": (m.now()+timedelta(days=1,hours=2)).isoformat(),
               "engineer_id": fixed("owner-a"), "reviewer_id": fixed("owner-a"), "equipment": "kit-a", "reason": "single owner v1.1"}
    batch = fixed("batch-a-VA")
    assert post(owner, f"/internal/batches/{batch}/schedule", payload).status_code == 200
    other_batch = fixed("batch-a-WVA")
    assert post(owner, f"/internal/batches/{other_batch}/schedule", payload).status_code == 409
    with platform["engine"].begin() as conn:
        change(conn, m.projects, fixed("tenant-a"), fixed("project-a"), requires_independent_review=True)
    future = {**payload, "start_at": (m.now()+timedelta(days=3)).isoformat(), "end_at": (m.now()+timedelta(days=3,hours=2)).isoformat()}
    assert post(owner, f"/internal/batches/{other_batch}/schedule", future).status_code == 409


def test_quote_version_acceptance_stale_rejected_and_course_standalone(platform):
    owner, customer = platform["login"]("owner-a"), platform["login"]()
    body = {"title": "七服務合成報價", "amount_minor": 120000, "services": ["VA", "WVA", "SHC", "PT", "SOURCE", "PHISHING", "TRAINING"],
            "valid_until": (m.now()+timedelta(days=7)).isoformat()}
    first = post(owner, "/internal/quotes", body).json()
    second = post(owner, f"/internal/quotes/{first['id']}/revise", {**body, "amount_minor": 130000}).json()
    assert post(customer, f"/customer/quotes/{first['id']}/accept", {"version": first["version"], "intent": "accept"}).status_code == 409
    assert post(customer, f"/customer/quotes/{second['id']}/accept", {"version": second["version"], "intent": "accept"}).status_code == 200
    assert len(customer.get("/customer/contracts").json()["items"]) == 1
    learner = platform["login"]("learner-a")
    assert post(learner, f"/customer/quotes/{second['id']}/accept", {"version": second["version"], "intent": "accept"}).status_code == 403
