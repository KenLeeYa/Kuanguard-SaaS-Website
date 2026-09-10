from datetime import timedelta
import json
from uuid import uuid4

import pytest

from kuanguard import models as m
from kuanguard.db import add, all_rows, change
from kuanguard.seed import fixed


@pytest.fixture
def operations(platform):
    from kuanguard.api import app
    from kuanguard.operations_routes import router
    original = list(app.router.routes)
    added = not any(getattr(route, "path", "") == "/customer/questionnaires" for route in original)
    if added:
        app.include_router(router)
    yield platform
    if added:
        app.router.routes[:] = original


def post(client, path, payload=None, key=None):
    return client.post(path, json=payload if payload is not None else {}, headers={"idempotency-key": key or str(uuid4())})


def questionnaire(client, questions=None, key=None):
    payload = {"title": "供應商問卷示範", "supplier": "合成供應商", "due_at": (m.now()+timedelta(days=7)).isoformat(),
               "questions": questions or ["是否保留還原測試紀錄？"]}
    response = post(client, "/customer/questionnaires", payload, key)
    assert response.status_code == 200, response.text
    return response.json(), payload


def answer(client, document, text="已提供管理程序與紀錄", reference="vault:synthetic/evidence-1", key=None):
    row = document["answers"][0]
    payload = {"answer": text, "evidence_reference": reference, "expected_revision": row["revision"]}
    response = post(client, f"/customer/questionnaires/{document['id']}/answers/{row['id']}", payload, key)
    assert response.status_code == 200, response.text
    return response.json(), payload


def review(client, document, decision="reviewed", reason="已檢視文字與參照，並非認證", key=None):
    row = document["answers"][0]
    payload = {"decision": decision, "reason": reason, "expected_revision": row["revision"]}
    return post(client, f"/internal/questionnaires/{document['id']}/answers/{row['id']}/review", payload, key), payload


def test_questionnaire_admin_answer_review_and_edit_invalidate_old_review(operations):
    customer, reviewer = operations["login"](), operations["login"]("reviewer-a")
    document, payload = questionnaire(customer)
    assert document["scope"] == "current_tenant" and "不構成認證" in document["notice"]
    assert document["answers"][0]["answer"] == document["answers"][0]["evidence_reference"] == ""
    assert document["status"] == "open" and document["overdue"] is False
    document, _ = answer(customer, document)
    response, _ = review(reviewer, document)
    assert response.status_code == 200
    document = response.json()
    assert document["status"] == "reviewed" and document["answers"][0]["review_status"] == "reviewed"
    document, _ = answer(customer, document, text="程序有更新，請重新覆核")
    assert document["status"] == "in_review" and document["answers"][0]["review_status"] == "unreviewed"
    assert document["title"] == payload["title"]


def test_questionnaires_and_reviews_reject_other_tenants_and_mixed_parent_ids(operations):
    a, b = operations["login"](), operations["login"]("customer-b")
    document, _ = questionnaire(a)
    other, _ = questionnaire(a, ["另一份問卷"])
    assert b.get("/customer/questionnaires").json()["items"] == []
    assert b.get(f"/customer/questionnaires/{document['id']}").status_code == 404
    row = document["answers"][0]
    payload = {"answer": "wrong scope", "expected_revision": row["revision"]}
    assert post(b, f"/customer/questionnaires/{document['id']}/answers/{row['id']}", payload).status_code == 404
    assert post(a, f"/customer/questionnaires/{other['id']}/answers/{row['id']}", payload).status_code == 404
    with operations["engine"].begin() as conn:
        add(conn, m.memberships, tenant_id=fixed("tenant-b"), user_id=fixed("customer-b"), role="reviewer", active=True)
    b_reviewer = operations["login"]("customer-b")
    assert b_reviewer.get("/internal/questionnaires").json()["items"] == []
    assert b_reviewer.get(f"/internal/questionnaires/{document['id']}").status_code == 404
    assert review(b_reviewer, document)[0].status_code == 404


@pytest.mark.parametrize("profile", ["learner-a", "engineer-a", "finance-a"])
def test_questionnaire_roles_are_explicit(operations, profile):
    client = operations["login"](profile)
    assert client.get("/customer/questionnaires").status_code == 403
    assert client.get("/internal/questionnaires").status_code == 403
    payload = {"title": "x", "supplier": "y", "due_at": m.now().isoformat(), "questions": ["q"]}
    assert post(client, "/customer/questionnaires", payload).status_code == 403


def test_portfolio_owner_role_does_not_imply_questionnaire_access(operations):
    with operations["engine"].begin() as conn:
        conn.execute(m.memberships.update().where(m.memberships.c.user_id == fixed("owner-a"),
            m.memberships.c.role != "portfolio_owner").values(active=False))
    owner = operations["login"]("owner-a")
    assert owner.get("/internal/questionnaires").status_code == 403
    assert owner.get("/customer/questionnaires").status_code == 403


def test_evidence_absence_is_not_approved_and_reference_is_inert_text(operations):
    customer, reviewer = operations["login"](), operations["login"]("reviewer-a")
    document, _ = questionnaire(customer)
    assert review(reviewer, document)[0].status_code == 409
    document, _ = answer(customer, document, reference="")
    assert review(reviewer, document)[0].status_code == 409
    response, _ = review(reviewer, document, decision="insufficient_evidence")
    assert response.status_code == 200 and response.json()["status"] == "in_review"
    reference = "https://example.invalid/internal-evidence?reference=unfetched <script>plain text</script>"
    updated, _ = answer(customer, response.json(), reference=reference)
    assert updated["answers"][0]["evidence_reference"] == reference
    assert review(reviewer, updated)[0].status_code == 200


def test_stale_reviewer_cannot_approve_changed_answer(operations):
    customer, reviewer = operations["login"](), operations["login"]("reviewer-a")
    document, _ = questionnaire(customer)
    viewed, _ = answer(customer, document)
    current, _ = answer(customer, viewed, text="答案已修訂")
    assert review(reviewer, viewed)[0].status_code == 409
    row = customer.get(f"/customer/questionnaires/{document['id']}").json()["answers"][0]
    assert row["revision"] == current["answers"][0]["revision"] and row["review_status"] == "unreviewed"


def test_replayed_review_reads_current_state_and_preserves_full_reason_audit(operations):
    customer, reviewer = operations["login"](), operations["login"]("reviewer-a")
    document, _ = questionnaire(customer)
    document, _ = answer(customer, document)
    key = str(uuid4())
    reason = "完整理由"*250
    response, payload = review(reviewer, document, reason=reason, key=key)
    assert response.status_code == 200
    updated, _ = answer(customer, response.json(), text="新版本等待覆核")
    row = document["answers"][0]
    replay = post(reviewer, f"/internal/questionnaires/{document['id']}/answers/{row['id']}/review", payload, key)
    assert replay.status_code == 200 and replay.json()["answers"][0]["review_status"] == "unreviewed"
    assert replay.json()["answers"][0]["revision"] == updated["answers"][0]["revision"]
    with operations["engine"].connect() as conn:
        events = all_rows(conn, m.audit_events, fixed("tenant-a"), m.audit_events.c.action == "questionnaire.review")
        assert len(events) == 1 and json.loads(events[0]["summary"])["reason"] == reason


def test_creation_replay_conflict_and_sql_pagination(operations):
    customer = operations["login"]()
    key = str(uuid4())
    first, payload = questionnaire(customer, key=key)
    replay = post(customer, "/customer/questionnaires", payload, key)
    assert replay.json()["id"] == first["id"]
    assert post(customer, "/customer/questionnaires", {**payload, "title": "different"}, key).status_code == 409
    questionnaire(customer)
    response = customer.get("/customer/questionnaires?page=2&page_size=1").json()
    assert response["total"] == 2 and response["page"] == 2 and len(response["items"]) == 1
    assert customer.get("/customer/questionnaires?page_size=101").status_code == 422
    assert customer.get("/customer/questionnaires?tenant_id=another").status_code == 422


@pytest.mark.parametrize("override", [{"tenant_id": "another"}, {"raw_file": "payload"}, {"upload_url": "https://example.invalid"}])
def test_questionnaire_raw_uploads_and_scope_overrides_are_rejected(operations, override):
    customer = operations["login"]()
    payload = {"title": "x", "supplier": "y", "due_at": m.now().isoformat(), "questions": ["q"], **override}
    assert post(customer, "/customer/questionnaires", payload).status_code == 422


def test_questionnaire_limits_timezone_csrf_and_idempotency(operations):
    customer = operations["login"]()
    payload = {"title": "x", "supplier": "y", "due_at": "2026-09-10T12:00:00", "questions": ["q"]}
    assert post(customer, "/customer/questionnaires", payload).status_code == 422
    payload["due_at"] = m.now().isoformat()
    assert post(customer, "/customer/questionnaires", {**payload, "questions": ["q"]*101}).status_code == 422
    assert customer.post("/customer/questionnaires", json=payload).status_code == 400
    assert customer.post("/customer/questionnaires", json=payload, headers={"idempotency-key": str(uuid4()), "x-csrf-token": "invalid"}).status_code == 403


def test_notifications_are_personal_and_read_replay_checks_current_ownership(operations):
    customer, learner, b = operations["login"](), operations["login"]("learner-a"), operations["login"]("customer-b")
    row = customer.get("/customer/notifications").json()["items"][0]
    assert learner.get("/customer/notifications").json()["items"] == []
    key = str(uuid4())
    read = post(customer, f"/customer/notifications/{row['id']}/read", key=key)
    assert read.status_code == 200 and read.json()["is_read"] is True
    assert post(customer, f"/customer/notifications/{row['id']}/read", key=key).json()["read_at"] == read.json()["read_at"]
    assert post(learner, f"/customer/notifications/{row['id']}/read").status_code == 404
    assert post(b, f"/customer/notifications/{row['id']}/read").status_code == 404
    with operations["engine"].begin() as conn:
        change(conn, m.notifications, fixed("tenant-a"), row["id"], user_id=fixed("learner-a"))
    assert post(customer, f"/customer/notifications/{row['id']}/read", key=key).status_code == 404
    assert len(learner.get("/customer/notifications").json()["items"]) == 1


def test_ticket_owner_visibility_and_pm_status_preserve_original_text(operations):
    customer, learner, other, pm = (operations["login"](profile) for profile in ["customer-a", "learner-a", "customer-b", "pm-a"])
    text = "原始工單內容不應被狀態操作覆寫。"
    ticket = post(customer, "/customer/tickets", {"subject": "測試工單", "text": text}).json()
    assert customer.get(f"/customer/tickets/{ticket['id']}").json()["text"] == text
    assert learner.get(f"/customer/tickets/{ticket['id']}").status_code == 404
    assert other.get(f"/customer/tickets/{ticket['id']}").status_code == 404
    assert pm.get("/internal/tickets").json()["total"] == 1
    payload = {"status": "closed", "expected_status": "open", "reason": "內部處理原因只保留於稽核"}
    key = str(uuid4())
    result = post(pm, f"/internal/tickets/{ticket['id']}/status", payload, key)
    assert result.status_code == 200 and result.json()["text"] == text
    assert result.json()["status"] == "closed"
    assert post(pm, f"/internal/tickets/{ticket['id']}/status", payload, key).status_code == 200
    assert post(pm, f"/internal/tickets/{ticket['id']}/status", payload).status_code == 409
    customer_view = customer.get(f"/customer/tickets/{ticket['id']}").json()
    assert customer_view["text"] == text and "reason" not in customer_view
    with operations["engine"].connect() as conn:
        events = all_rows(conn, m.audit_events, fixed("tenant-a"), m.audit_events.c.action == "ticket.status")
        assert len(events) == 1 and json.loads(events[0]["summary"])["reason"] == payload["reason"]


def test_ticket_internal_role_and_tenant_limits(operations):
    customer, b, pm, reviewer = (operations["login"](profile) for profile in ["customer-a", "customer-b", "pm-a", "reviewer-a"])
    ticket = post(b, "/customer/tickets", {"subject": "企業 B 工單", "text": "限本企業"}).json()
    assert customer.get("/internal/tickets").status_code == 403
    assert reviewer.get("/internal/tickets").status_code == 403
    assert pm.get("/internal/tickets").json()["items"] == []
    assert pm.get(f"/internal/tickets/{ticket['id']}").status_code == 404
    assert post(pm, f"/internal/tickets/{ticket['id']}/status", {"status": "closed", "expected_status": "open", "reason": "wrong tenant"}).status_code == 404
    assert pm.get("/internal/tickets?tenant_id=another").status_code == 422
