"""LMS seat and legacy point authorizations use isolated fixture databases."""
from datetime import timedelta
from uuid import uuid4
import json

import pytest

from kuanguard import learning_entitlements as seats, models as m, wallet, worker
from kuanguard.db import add, all_rows, change, one
from kuanguard.seed import fixed
from test_platform import post


@pytest.fixture
def training_platform(platform):
    seats.training_metadata.create_all(platform["engine"])
    return platform


@pytest.fixture
def clock(monkeypatch):
    current = [m.now()]
    monkeypatch.setattr(m, "now", lambda: current[0])
    return current


def grant(platform, *, source="gift", quantity=1, cohort=None, duration=timedelta(days=30), **extra):
    body = {"course_id": fixed("course"), "source": source, "quantity": quantity, "cohort": cohort,
            "starts_at": (m.now()-timedelta(minutes=1)).isoformat(), "expires_at": (m.now()+duration).isoformat(),
            "source_reference": f"synthetic-approved-{uuid4()}", "reason": "合成資料：核定有限教育訓練席次"}
    if source == "annual_included":
        with platform["engine"].begin() as conn:
            contract = add(conn, m.contracts, fixed("tenant-a"), title="合成年度方案", status="active")
        body["contract_id"] = contract["id"]
    body.update(extra)
    response = post(platform["login"]("pm-a"), "/internal/training/entitlements", body)
    assert response.status_code == 200, response.text
    return response.json()


def assign(client, *, learner="learner-a", cohort="seat-2026", course_id=None, key=None):
    return post(client, "/customer/training/enrollments", {
        "course_id": course_id or fixed("course"), "learner_id": fixed(learner), "cohort": cohort,
    }, key=key)


def entries(platform, enrollment_id):
    with platform["engine"].connect() as conn:
        rows = all_rows(conn, seats.ledger, fixed("tenant-a"), seats.ledger.c.enrollment_id == enrollment_id)
        return sorted(rows, key=lambda row: (row["created_at"], row["kind"] != "reserve"))


@pytest.mark.parametrize("source", ["annual_included", "gift", "manual"])
def test_each_seat_source_reserves_and_consumes_once_without_wallet(training_platform, monkeypatch, source):
    platform = training_platform
    entitlement = grant(platform, source=source)
    customer = platform["login"]()
    before = customer.get("/customer/wallet").json()

    def unexpected_wallet(*args, **kwargs):
        raise AssertionError("seat authorization must never reserve or consume wallet points")

    monkeypatch.setattr(wallet, "reserve", unexpected_wallet)
    monkeypatch.setattr(wallet, "consume", unexpected_wallet)
    first = assign(customer)
    assert first.status_code == 200, first.text
    enrollment = first.json()
    assert enrollment["reservation_id"] is None and enrollment["source"] == source
    assert enrollment["authorization"]["entitlement_id"] == entitlement["id"]
    assert assign(customer).json()["id"] == enrollment["id"]
    learner = platform["login"]("learner-a")
    for _ in range(2):
        started = post(learner, f"/learner/enrollments/{enrollment['id']}/start")
        assert started.status_code == 200, started.text
    assert [row["kind"] for row in entries(platform, enrollment["id"])] == ["reserve", "consume"]
    summary = customer.get("/customer/training/entitlements").json()["items"][0]
    assert (summary["available"], summary["reserved"], summary["consumed"]) == (0, 0, 1)
    after = customer.get("/customer/wallet").json()
    assert [after[key] for key in ("available", "reserved", "consumed", "transaction_total")] == [
        before[key] for key in ("available", "reserved", "consumed", "transaction_total")]


def test_capacity_exhaustion_uses_points_and_unstarted_cancellation_reuses_seat(training_platform):
    platform = training_platform
    entitlement = grant(platform)
    customer = platform["login"]()
    first = assign(customer).json()
    second = assign(customer, learner="learner-a2").json()
    assert first["reservation_id"] is None and second["reservation_id"]
    assert customer.get("/customer/wallet").json()["reserved"] == 10
    for _ in range(2):
        assert post(customer, f"/customer/training/enrollments/{first['id']}/cancel").status_code == 200
    third = assign(customer, cohort="seat-2027").json()
    assert third["authorization"]["entitlement_id"] == entitlement["id"] and third["id"] != first["id"]
    assert [row["kind"] for row in entries(platform, first["id"])] == ["reserve", "release"]
    assert customer.get("/customer/wallet").json()["reserved"] == 10
    assert post(customer, f"/customer/training/enrollments/{second['id']}/cancel").status_code == 200
    assert customer.get("/customer/wallet").json()["reserved"] == 0
    assert assign(customer).status_code == 409


def test_first_expiry_course_cohort_and_tenant_boundaries(training_platform):
    platform = training_platform
    customer = platform["login"]()
    other = platform["login"]("customer-b")
    grant(platform, cohort="other-year", duration=timedelta(days=1))
    later = grant(platform, duration=timedelta(days=40))
    sooner = grant(platform, duration=timedelta(days=2))
    selected = assign(customer).json()
    assert selected["authorization"]["entitlement_id"] == sooner["id"]
    assert selected["expires_at"] == sooner["expires_at"]
    assert assign(customer, learner="learner-a2").json()["authorization"]["entitlement_id"] == later["id"]
    assert assign(other, learner="learner-b").json()["source"] == "points"
    assert not other.get("/customer/training/entitlements").json()["items"]
    with platform["engine"].begin() as conn:
        original = one(conn, m.courses, None, m.courses.c.id == fixed("course"))
        cloned = {key: value for key, value in original.items() if key not in {"id", "created_at", "slug"}}
        new_course = add(conn, m.courses, slug="synthetic-other-course", **cloned)
    assert assign(customer, course_id=new_course["id"]).json()["source"] == "points"


def test_expired_and_future_grants_are_not_used(training_platform, clock):
    platform = training_platform
    expired = grant(platform, duration=timedelta(minutes=5))
    grant(platform, starts_at=(clock[0]+timedelta(days=1)).isoformat())
    clock[0] += timedelta(minutes=6)
    customer = platform["login"]()
    assigned = assign(customer).json()
    assert assigned["source"] == "points"
    listed = customer.get("/customer/training/entitlements").json()["items"]
    assert {row["status"] for row in listed} == {"expired", "scheduled"}
    assert all(row["available"] == 0 for row in listed)
    assert expired["quantity"] == 1


def test_new_assignment_reuses_expired_unstarted_hold_before_worker_runs(training_platform, clock, monkeypatch):
    platform = training_platform
    entitlement = grant(platform, duration=timedelta(days=90))
    first = assign(platform["login"](), cohort="2026").json()
    clock[0] += timedelta(days=15)

    def unexpected_wallet(*args, **kwargs):
        raise AssertionError("expired unstarted seat must be released before point fallback")

    monkeypatch.setattr(wallet, "reserve", unexpected_wallet)
    again = assign(platform["login"](), cohort="2027")
    assert again.status_code == 200, again.text
    assert again.json()["authorization"]["entitlement_id"] == entitlement["id"]
    assert [row["kind"] for row in entries(platform, first["id"])] == ["reserve", "release"]
    with platform["engine"].connect() as conn:
        assert one(conn, m.enrollments, fixed("tenant-a"), m.enrollments.c.id == first["id"])["status"] == "expired"


def test_expiry_releases_unstarted_seats_and_points_once_but_retains_consumed(training_platform, clock):
    platform = training_platform
    grant(platform, quantity=2, duration=timedelta(minutes=5))
    customer = platform["login"]()
    assigned = assign(customer).json()
    active = assign(customer, learner="learner-a2").json()
    paid = assign(customer, cohort="paid").json()
    learner = platform["login"]("learner-a2")
    assert post(learner, f"/learner/enrollments/{active['id']}/start").status_code == 200
    with platform["engine"].begin() as conn:
        change(conn, m.enrollments, fixed("tenant-a"), paid["id"], expires_at=clock[0]+timedelta(minutes=5))
    clock[0] += timedelta(minutes=6)
    worker.expire_training()
    worker.expire_training()
    with platform["engine"].connect() as conn:
        assert one(conn, m.enrollments, fixed("tenant-a"), m.enrollments.c.id == assigned["id"])["status"] == "expired"
        assert one(conn, m.enrollments, fixed("tenant-a"), m.enrollments.c.id == active["id"])["status"] == "active"
        assert one(conn, m.reservations, fixed("tenant-a"), m.reservations.c.id == paid["reservation_id"])["status"] == "released"
    assert [row["kind"] for row in entries(platform, assigned["id"])] == ["reserve", "release"]
    assert [row["kind"] for row in entries(platform, active["id"])] == ["reserve", "consume"]
    summary = customer.get("/customer/training/entitlements").json()["items"][0]
    assert (summary["status"], summary["available"], summary["reserved"], summary["consumed"]) == ("expired", 0, 0, 1)
    assert post(learner, f"/learner/enrollments/{active['id']}/start").status_code == 410
    assert learner.get(f"/learner/enrollments/{active['id']}/lessons").status_code == 410


def test_inactive_learner_membership_denies_access_and_worker_releases_only_unstarted(training_platform):
    platform = training_platform
    grant(platform, quantity=2)
    customer, learner = platform["login"](), platform["login"]("learner-a")
    assigned = assign(customer).json()
    active = assign(customer, cohort="started").json()
    paid = assign(customer, cohort="paid").json()
    assert post(learner, f"/learner/enrollments/{active['id']}/start").status_code == 200
    with platform["engine"].begin() as conn:
        learner_member = one(conn, m.memberships, None, m.memberships.c.user_id == fixed("learner-a"),
                             m.memberships.c.tenant_id == fixed("tenant-a"), m.memberships.c.role == "learner")
        change(conn, m.memberships, None, learner_member["id"], active=False)
        add(conn, m.memberships, tenant_id=fixed("tenant-a"), user_id=fixed("learner-a"), role="customer_contact", active=True)
        add(conn, m.memberships, tenant_id=fixed("tenant-b"), user_id=fixed("learner-a"), role="learner", active=True)
    # Another role and another tenant's learner membership cannot retain this tenant's learner access.
    assert learner.get(f"/learner/enrollments/{active['id']}").status_code == 403
    assert post(learner, f"/learner/enrollments/{active['id']}/start").status_code == 403
    assert assign(customer, cohort="after-disable").status_code == 404
    worker.expire_training()
    worker.expire_training()
    assert [row["kind"] for row in entries(platform, assigned["id"])] == ["reserve", "release"]
    assert [row["kind"] for row in entries(platform, active["id"])] == ["reserve", "consume"]
    with platform["engine"].connect() as conn:
        assert one(conn, m.reservations, fixed("tenant-a"), m.reservations.c.id == paid["reservation_id"])["status"] == "released"
        assert one(conn, m.users, None, m.users.c.id == fixed("learner-a"))["active"] is True
        assert one(conn, m.enrollments, fixed("tenant-a"), m.enrollments.c.id == active["id"])["status"] == "active"


def test_offboarding_helper_is_idempotent_and_does_not_touch_other_tenant(training_platform):
    platform = training_platform
    grant(platform)
    customer = platform["login"]()
    enrollment = assign(customer).json()
    with platform["engine"].begin() as conn:
        assert seats.release_unstarted_for_learner(conn, fixed("tenant-b"), fixed("learner-a"), "wrong tenant") == []
        assert seats.release_unstarted_for_learner(conn, fixed("tenant-a"), fixed("learner-a"), "offboard") == [enrollment["id"]]
        assert seats.release_unstarted_for_learner(conn, fixed("tenant-a"), fixed("learner-a"), "offboard replay") == []
    assert [row["kind"] for row in entries(platform, enrollment["id"])] == ["reserve", "release"]


def test_grant_roles_csrf_validation_and_idempotency(training_platform):
    platform = training_platform
    pm = platform["login"]("pm-a")
    body = {"course_id": fixed("course"), "source": "manual", "quantity": 1,
            "starts_at": m.now().isoformat(), "expires_at": (m.now()+timedelta(days=30)).isoformat(),
            "source_reference": "synthetic-manual-receipt", "reason": "明示人工核發一席"}
    key = str(uuid4())
    first = post(pm, "/internal/training/entitlements", body, key=key)
    assert first.status_code == 200, first.text
    assert post(pm, "/internal/training/entitlements", body, key=key).json()["id"] == first.json()["id"]
    assert post(pm, "/internal/training/entitlements", {**body, "quantity": 2}, key=key).status_code == 409
    for profile in ["customer-a", "learner-a", "finance-a", "reviewer-a"]:
        assert post(platform["login"](profile), "/internal/training/entitlements", body).status_code == 403
    assert pm.post("/internal/training/entitlements", json=body, headers={"idempotency-key": str(uuid4()), "x-csrf-token": "forged"}).status_code == 403
    assert post(pm, "/internal/training/entitlements", {**body, "tenant_id": fixed("tenant-b")}).status_code == 422
    for quantity in [0, -1, True, 1.5, 100001]:
        assert post(pm, "/internal/training/entitlements", {**body, "quantity": quantity}).status_code == 422
    assert post(pm, "/internal/training/entitlements", {**body, "source": "points"}).status_code == 422
    assert post(pm, "/internal/training/entitlements", {**body, "starts_at": "2026-09-10T00:00:00"}).status_code == 422
    assert post(pm, "/internal/training/entitlements", {**body, "expires_at": body["starts_at"]}).status_code == 422
    assert post(pm, "/internal/training/entitlements", {**body, "source": "annual_included"}).status_code == 422
    with platform["engine"].begin() as conn:
        other_contract = add(conn, m.contracts, fixed("tenant-b"), title="其他租戶合約", status="active")
        inactive_contract = add(conn, m.contracts, fixed("tenant-a"), title="已失效合約", status="cancelled")
    for contract in [other_contract, inactive_contract]:
        assert post(pm, "/internal/training/entitlements", {**body, "source": "annual_included", "contract_id": contract["id"]}).status_code == 404


def test_bounded_catalog_lists_and_preview_are_read_only(training_platform):
    platform = training_platform
    entitlement = grant(platform, source="annual_included")
    pm, customer = platform["login"]("pm-a"), platform["login"]()
    for path in ["/internal/training/courses", "/internal/training/contracts", "/internal/training/entitlements"]:
        result = pm.get(path, params={"page_size": 1})
        assert result.status_code == 200 and result.json()["page_size"] == 1
        assert pm.get(path, params={"page_size": 101}).status_code == 422
        assert pm.get(path, params={"tenant_id": fixed("tenant-b")}).status_code == 422
        assert customer.get(path).status_code == 403
    params = {"course_id": fixed("course"), "learner_id": fixed("learner-a"), "cohort": "preview"}
    path = "/customer/training/assignment-preview"
    for _ in range(2):
        result = customer.get(path, params=params)
        assert result.status_code == 200, result.text
        assert result.json()["entitlement_id"] == entitlement["id"] and result.json()["preview"] is True
    assert customer.get("/customer/training/entitlements").json()["items"][0]["available"] == 1
    assert customer.get("/customer/wallet").json()["reserved"] == 0
    assigned = assign(customer, cohort="preview").json()
    result = customer.get(path, params=params).json()
    assert result["existing_enrollment_id"] == assigned["id"]
    assert result["quantity"] == 1 and result["unit"] == "enrollment_seat"
    assert customer.get(path, params={**params, "learner_id": fixed("learner-b")}).status_code == 404
    assert customer.get(path, params={**params, "tenant_id": fixed("tenant-b")}).status_code == 422
    assert platform["login"]("learner-a").get(path, params=params).status_code == 403


def test_existing_point_enrollment_is_preserved_when_later_seat_granted(training_platform):
    platform = training_platform
    customer = platform["login"]()
    before = assign(customer).json()
    entitlement = grant(platform)
    again = assign(customer).json()
    assert again["id"] == before["id"] and again["reservation_id"] == before["reservation_id"]
    assert again["source"] == "points" and again["authorization"]["entitlement_id"] is None
    assert customer.get("/customer/training/entitlements").json()["items"][0]["available"] == 1
    assert assign(customer, cohort="2027").json()["authorization"]["entitlement_id"] == entitlement["id"]


def test_failed_start_rolls_back_seat_consumption_and_retries_once(training_platform, monkeypatch):
    from kuanguard import learning_routes
    platform = training_platform
    grant(platform)
    customer, learner = platform["login"](), platform["login"]("learner-a")
    enrollment = assign(customer).json()
    original = learning_routes.change

    def fail_activation(conn, table, tenant, resource_id, **values):
        if table is m.enrollments and values.get("status") == "active":
            raise RuntimeError("synthetic activation failure")
        return original(conn, table, tenant, resource_id, **values)

    monkeypatch.setattr(learning_routes, "change", fail_activation)
    with pytest.raises(RuntimeError, match="synthetic activation failure"):
        post(learner, f"/learner/enrollments/{enrollment['id']}/start")
    assert [row["kind"] for row in entries(platform, enrollment["id"])] == ["reserve"]
    monkeypatch.setattr(learning_routes, "change", original)
    assert post(learner, f"/learner/enrollments/{enrollment['id']}/start").status_code == 200
    assert [row["kind"] for row in entries(platform, enrollment["id"])] == ["reserve", "consume"]


def test_retraining_keeps_old_certificate_and_offboarding_does_not_erase_history(training_platform):
    platform = training_platform
    grant(platform, quantity=2)
    customer, learner = platform["login"](), platform["login"]("learner-a")
    old = assign(customer, cohort="2026").json()
    assert post(learner, f"/learner/enrollments/{old['id']}/start").status_code == 200
    with platform["engine"].begin() as conn:
        change(conn, m.enrollments, fixed("tenant-a"), old["id"], started_at=m.now()-timedelta(minutes=10))
        lessons = all_rows(conn, m.lessons, None, m.lessons.c.course_id == fixed("course"))
        questions = all_rows(conn, m.questions, None, m.questions.c.course_id == fixed("course"))
    for lesson in lessons:
        assert post(learner, f"/learner/enrollments/{old['id']}/progress", {"lesson_id": lesson["id"], "seconds": lesson["min_seconds"]}).status_code == 200
    result = post(learner, "/learner/attempts", {"enrollment_id": old["id"], "answers": [
        {"question_id": question["id"], "choice": question["correct_choice"]} for question in questions]})
    assert result.status_code == 200 and result.json()["passed"], result.text
    certificate_id = result.json()["certificate_id"]
    new = assign(customer, cohort="2027").json()
    assert old["id"] != new["id"] and new["status"] == "assigned"
    assert learner.get(f"/learner/certificates/{certificate_id}").status_code == 200
    deactivated = post(customer, f"/customer/training/learners/{fixed('learner-a')}/deactivate", {"reason": "學員離職，保留既有學習證明"})
    assert deactivated.status_code == 200 and deactivated.json()["released_enrollment_ids"] == [new["id"]]
    assert learner.get(f"/learner/certificates/{certificate_id}").status_code == 401
    with platform["engine"].connect() as conn:
        assert one(conn, m.enrollments, fixed("tenant-a"), m.enrollments.c.id == old["id"])["status"] == "completed"
        assert one(conn, m.certificates, fixed("tenant-a"), m.certificates.c.id == certificate_id)
        assert len(all_rows(conn, m.attempts, fixed("tenant-a"), m.attempts.c.enrollment_id == old["id"])) == 1
    assert customer.get(f"/public/certificates/{certificate_id}").json()["valid"] is True


@pytest.mark.parametrize("kind", ["report", "planned_mail", "unknown_mail"])
def test_inactive_tenant_jobs_do_not_run_and_unknown_reservations_remain(training_platform, clock, monkeypatch, kind):
    from kuanguard import reports
    from test_worker_recovery import mail_job, report_job
    platform = training_platform
    tenant = fixed("tenant-a")
    if kind == "report":
        job, report = report_job(platform, clock)
    else:
        job, message, reservation, _ = mail_job(platform, clock, message_status="unknown" if kind == "unknown_mail" else "planned")
    with platform["engine"].begin() as conn:
        change(conn, m.tenants, None, tenant, status="inactive")

    def no_render(*args, **kwargs):
        raise AssertionError("inactive tenant must not render reports")

    monkeypatch.setattr(reports, "generate_bundle", no_render)
    assert worker.process_once() is None
    with platform["engine"].begin() as conn:
        stored = one(conn, m.jobs, None, m.jobs.c.id == job["id"])
        assert stored["status"] == "cancelled" and stored["error_code"] == "TENANT_INACTIVE"
        assert stored["claim_token"] is None and stored["attempts"] == 0
        if kind == "report":
            assert one(conn, m.report_jobs, tenant, m.report_jobs.c.id == report["id"])["status"] == "cancelled"
        else:
            assert one(conn, m.message_plans, tenant, m.message_plans.c.id == message["id"])["status"] == (
                "unknown" if kind == "unknown_mail" else "cancelled")
            assert one(conn, m.reservations, tenant, m.reservations.c.id == reservation["id"])["status"] == (
                "reserved" if kind == "unknown_mail" else "released")
        change(conn, m.tenants, None, tenant, status="active")
    assert worker.process_once() is None


def test_worker_prunes_expired_form_drafts_without_payload_audit(training_platform, clock):
    platform = training_platform
    with platform["engine"].begin() as conn:
        for suffix in ["a", "b"]:
            for label, offset in [("expired", -1), ("valid", 1)]:
                add(conn, m.form_drafts, fixed(f"tenant-{suffix}"), actor_id=fixed(f"customer-{suffix}"),
                    kind="questionnaire", draft_key=label, version=1, payload={"text": "synthetic sensitive draft"},
                    updated_at=clock[0]-timedelta(days=1), expires_at=clock[0]+timedelta(minutes=offset))
    worker.expire_training()
    worker.expire_training()
    with platform["engine"].connect() as conn:
        for suffix in ["a", "b"]:
            rows = all_rows(conn, m.form_drafts, fixed(f"tenant-{suffix}"))
            assert len(rows) == 1 and rows[0]["draft_key"] == "valid"
            assert all("synthetic sensitive draft" not in row["summary"] for row in all_rows(conn, m.audit_events, fixed(f"tenant-{suffix}")))


def test_deactivate_learner_releases_unstarted_only_and_preserves_other_memberships(training_platform):
    platform = training_platform
    grant(platform, quantity=2)
    customer, learner = platform["login"](), platform["login"]("learner-a")
    pending = assign(customer).json()
    active = assign(customer, cohort="active").json()
    paid = assign(customer, cohort="paid").json()
    assert post(learner, f"/learner/enrollments/{active['id']}/start").status_code == 200
    with platform["engine"].begin() as conn:
        other_role = add(conn, m.memberships, tenant_id=fixed("tenant-a"), user_id=fixed("learner-a"), role="customer_contact", active=True)
        other_tenant = add(conn, m.memberships, tenant_id=fixed("tenant-b"), user_id=fixed("learner-a"), role="learner", active=True)
    path = f"/customer/training/learners/{fixed('learner-a')}/deactivate"
    key, reason = str(uuid4()), "離職原因"*250
    first = post(customer, path, {"reason": reason}, key=key)
    assert first.status_code == 200, first.text
    assert first.json()["active"] is False
    assert set(first.json()["released_enrollment_ids"]) == {pending["id"], paid["id"]}
    assert post(customer, path, {"reason": reason}, key=key).json() == first.json()
    assert post(customer, path, {"reason": reason}).json()["released_enrollment_ids"] == []
    assert post(customer, path, {"reason": "不同內容"}, key=key).status_code == 409
    assert fixed("learner-a") not in {row["id"] for row in customer.get("/customer/training/learners").json()["items"]}
    assert assign(customer, cohort="after-deactivation").status_code == 404
    assert learner.get(f"/learner/enrollments/{active['id']}").status_code == 403
    assert post(learner, f"/learner/enrollments/{active['id']}/start").status_code == 403
    with platform["engine"].connect() as conn:
        for membership in [other_role, other_tenant]:
            assert one(conn, m.memberships, None, m.memberships.c.id == membership["id"])["active"] is True
        assert one(conn, m.users, None, m.users.c.id == fixed("learner-a"))["active"] is True
        assert one(conn, m.enrollments, fixed("tenant-a"), m.enrollments.c.id == active["id"])["status"] == "active"
        assert one(conn, m.reservations, fixed("tenant-a"), m.reservations.c.id == paid["reservation_id"])["status"] == "released"
        audit = one(conn, m.audit_events, fixed("tenant-a"), m.audit_events.c.action == "training.learner.deactivate")
        assert json.loads(audit["summary"])["reason"] == reason
    assert [row["kind"] for row in entries(platform, pending["id"])] == ["reserve", "release"]
    assert [row["kind"] for row in entries(platform, active["id"])] == ["reserve", "consume"]


def test_department_change_checks_expected_value_and_retains_audit_and_course_authorization(training_platform):
    platform = training_platform
    grant(platform)
    customer = platform["login"]()
    enrollment = assign(customer).json()
    with platform["engine"].begin() as conn:
        original = one(conn, m.memberships, None, m.memberships.c.user_id == fixed("learner-a"), m.memberships.c.role == "learner")
        change(conn, m.memberships, None, original["id"], department=" 舊部門 ")
        other_tenant = add(conn, m.memberships, tenant_id=fixed("tenant-b"), user_id=fixed("learner-a"), role="learner", department="其他企業部門", active=True)
    listed = next(row for row in customer.get("/customer/training/learners").json()["items"] if row["id"] == fixed("learner-a"))
    path = f"/customer/training/learners/{fixed('learner-a')}/department"
    body = {"department": "資安部", "expected_department": listed["department"], "reason": "組織調整"}
    key = str(uuid4())
    changed = post(customer, path, body, key=key)
    assert changed.status_code == 200 and changed.json()["department"] == "資安部"
    assert post(customer, path, body, key=key).json()["department"] == "資安部"
    stale = post(customer, path, {**body, "department": "舊畫面部門"})
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "DEPARTMENT_CHANGED"
    assert post(customer, path, {"department": "營運部", "expected_department": "資安部", "reason": "後續調整"}).status_code == 200
    assert post(customer, path, body, key=key).json()["department"] == "營運部"
    with platform["engine"].connect() as conn:
        assert one(conn, m.memberships, None, m.memberships.c.id == other_tenant["id"])["department"] == "其他企業部門"
        assert one(conn, m.enrollments, fixed("tenant-a"), m.enrollments.c.id == enrollment["id"])["status"] == "assigned"
        audits = all_rows(conn, m.audit_events, fixed("tenant-a"), m.audit_events.c.action == "training.learner.department")
        assert len(audits) == 2
        first = next(row for row in audits if json.loads(row["summary"])["department"] == "資安部")
        assert json.loads(first["summary"])["previous_department"] == listed["department"]
    assert [row["kind"] for row in entries(platform, enrollment["id"])] == ["reserve"]


@pytest.mark.parametrize("action,payload", [
    ("deactivate", {"reason": "離職"}),
    ("department", {"department": "新部門", "expected_department": "", "reason": "調動"}),
])
def test_learner_management_requires_customer_admin_and_current_tenant(training_platform, action, payload):
    platform = training_platform
    path = f"/customer/training/learners/{fixed('learner-a')}/{action}"
    for profile in ["pm-a", "finance-a", "reviewer-a", "learner-a"]:
        assert post(platform["login"](profile), path, payload).status_code == 403
    customer = platform["login"]()
    assert post(customer, f"/customer/training/learners/{fixed('learner-b')}/{action}", payload).status_code == 404
    assert post(customer, path, {**payload, "tenant_id": fixed("tenant-b")}).status_code == 422
    assert post(customer, path, {**payload, "reason": " "}).status_code == 422
    assert customer.post(path, json=payload, headers={"x-csrf-token": "forged", "idempotency-key": str(uuid4())}).status_code == 403
    # training_manager alone can list/assign, but cannot deactivate or alter learner membership.
    with platform["engine"].begin() as conn:
        administrator = one(conn, m.memberships, None, m.memberships.c.user_id == fixed("customer-a"), m.memberships.c.role == "customer_admin")
        change(conn, m.memberships, None, administrator["id"], active=False)
    assert customer.get("/customer/training/learners").status_code == 200
    assert post(customer, path, payload).status_code == 403


def test_customer_admin_only_can_list_and_deactivate_but_cannot_assign(training_platform):
    platform = training_platform
    customer = platform["login"]()
    with platform["engine"].begin() as conn:
        manager = one(conn, m.memberships, None, m.memberships.c.user_id == fixed("customer-a"), m.memberships.c.role == "training_manager")
        change(conn, m.memberships, None, manager["id"], active=False)
    assert customer.get("/customer/training/learners").status_code == 200
    assert assign(customer).status_code == 403
    deactivated = post(customer, f"/customer/training/learners/{fixed('learner-a')}/deactivate", {"reason": "離職"})
    assert deactivated.status_code == 200
    changed = post(customer, f"/customer/training/learners/{fixed('learner-a')}/department", {
        "department": "新部門", "expected_department": deactivated.json()["department"], "reason": "停用後修改"})
    assert changed.status_code == 404
