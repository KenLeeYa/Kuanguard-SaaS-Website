from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete

from kuanguard import execution_models as e, models as m
from kuanguard.db import add, all_rows, change, one
from kuanguard.seed import fixed


PROJECT = fixed("project-a")
BATCH = fixed("batch-a-VA")
TENANT = fixed("tenant-a")


def post(client, path, data, key=None):
    return client.post(path, json=data, headers={"idempotency-key": key or str(uuid4())})


def task(client, **overrides):
    response = post(client, f"/internal/projects/{PROJECT}/tasks", {"title": "synthetic task", **overrides})
    assert response.status_code == 200, response.text
    return response.json()


def update_task(client, row, **overrides):
    keys = ("title", "status", "visibility", "customer_note", "internal_note", "batch_id", "assigned_to", "due_at", "dependency_ids")
    payload = {key: row[key] for key in keys}
    return post(client, f"/internal/tasks/{row['id']}", {**payload, "expected_version": row["version"], **overrides})


def schedule(**overrides):
    start = m.now() + timedelta(days=5)
    return {"start_at": start.isoformat(), "end_at": (start + timedelta(hours=1)).isoformat(),
            "engineer_id": fixed("owner-a"), "reviewer_id": fixed("owner-a"),
            "equipment": "test-kit", "reason": "explicit synthetic scheduling", **overrides}


def test_customer_projection_hides_notes_internal_dependencies_and_decisions(platform):
    owner, customer = platform["login"]("owner-a"), platform["login"]()
    hidden = task(owner, title="INTERNAL-SECRET", internal_note="SECRET-NOTE")
    shown = task(owner, title="customer work", visibility="customer", customer_note="公開說明",
                 internal_note="SECRET-NOTE", dependency_ids=[hidden["id"]])
    response = post(owner, f"/internal/projects/{PROJECT}/decisions", {
        "title": "visible decision", "occurred_at": m.now().isoformat(), "visibility": "customer",
        "customer_text": "meeting decision", "internal_note": "SECRET-NOTE", "batch_id": BATCH,
        "task_ids": [hidden["id"], shown["id"]]})
    assert response.status_code == 200, response.text
    assert response.json()["scope_version"] == 1
    private = post(owner, f"/internal/projects/{PROJECT}/decisions", {
        "title": "INTERNAL-DECISION", "occurred_at": m.now().isoformat(), "internal_note": "SECRET-NOTE"})
    assert private.status_code == 200
    for path in (f"/customer/projects/{PROJECT}/tasks", f"/customer/projects/{PROJECT}/decisions", f"/customer/projects/{PROJECT}"):
        result = customer.get(path)
        assert result.status_code == 200
        assert "SECRET-NOTE" not in result.text and "INTERNAL-" not in result.text and hidden["id"] not in result.text
        assert "internal_note" not in result.text
    visible = next(row for row in customer.get(f"/customer/projects/{PROJECT}/tasks").json()["items"] if row["id"] == shown["id"])
    assert visible["effective_status"] == "blocked" and visible["dependency_ids"] == []
    assert "assigned_to" not in visible
    assert customer.get(f"/customer/projects/{PROJECT}/decisions").json()["items"][0]["task_ids"] == [shown["id"]]


def test_dependencies_completion_cycle_reopen_and_stale_version(platform):
    owner = platform["login"]("owner-a")
    first = task(owner)
    second = task(owner, dependency_ids=[first["id"]])
    assert update_task(owner, first, dependency_ids=[second["id"]]).json()["detail"]["code"] == "DEPENDENCY_CYCLE"
    assert update_task(owner, first, dependency_ids=[first["id"]]).json()["detail"]["code"] == "DEPENDENCY_CYCLE"
    assert update_task(owner, second, status="done").json()["detail"]["code"] == "DEPENDENCY_BLOCKED"
    done_first = update_task(owner, first, status="done").json()
    assert done_first["version"] == 2
    done_second = update_task(owner, second, status="done").json()
    assert done_second["status"] == "done"
    assert update_task(owner, done_first, status="open").json()["detail"]["code"] == "COMPLETED_DEPENDENT"
    assert update_task(owner, first, title="stale overwrite").json()["detail"]["code"] == "STALE_VERSION"
    assert update_task(owner, done_second, status="open").status_code == 200
    assert update_task(owner, done_first, status="blocked", internal_note="waiting for answer").status_code == 200


def test_task_mutation_idempotency_and_project_role_boundaries(platform):
    owner, customer, engineer = [platform["login"](profile) for profile in ("owner-a", "customer-a", "engineer-a")]
    key, path = str(uuid4()), f"/internal/projects/{PROJECT}/tasks"
    first = post(owner, path, {"title": "retry-safe"}, key)
    assert first.status_code == 200
    assert post(owner, path, {"title": "retry-safe"}, key).json() == first.json()
    assert post(owner, path, {"title": "changed"}, key).status_code == 409
    assert post(customer, path, {"title": "customer mutation"}).status_code == 403
    assert post(engineer, path, {"title": "engineer mutation"}).status_code == 403
    assert engineer.get(path).status_code == 200
    assert platform["login"]("customer-b").get(f"/customer/projects/{PROJECT}/tasks").status_code == 404
    assert post(owner, f"/internal/projects/{fixed('project-b')}/tasks", {"title": "cross tenant"}).status_code == 404
    assert post(owner, path, {"title": "foreign batch", "batch_id": fixed("batch-b-VA")}).status_code == 404
    assert post(owner, path, {"title": "foreign assignee", "assigned_to": fixed("learner-b")}).status_code == 422
    assert post(owner, path, {"title": "timezone absent", "due_at": "2026-10-10T10:00:00"}).status_code == 422
    assert post(owner, path, {"title": "manual block", "status": "blocked"}).status_code == 422


def test_task_and_decision_links_do_not_cross_project_or_tenant(platform):
    owner = platform["login"]("owner-a")
    own = task(owner)
    another = post(owner, "/internal/projects", {"name": "another", "company_name": "synthetic", "year": 2026}).json()
    cross = post(owner, f"/internal/projects/{another['id']}/tasks", {"title": "other project"}).json()
    result = update_task(owner, own, dependency_ids=[cross["id"]])
    assert result.status_code == 404
    for body in ({"task_ids": [cross["id"]]}, {"batch_id": fixed("batch-b-VA")}, {"publication_id": str(uuid4())}):
        response = post(owner, f"/internal/projects/{PROJECT}/decisions", {
            "title": "bad link", "occurred_at": m.now().isoformat(), "internal_note": "note", **body})
        assert response.status_code == 404
    response = post(owner, f"/internal/projects/{PROJECT}/decisions", {
        "title": "missing public text", "occurred_at": m.now().isoformat(), "visibility": "customer", "internal_note": "private"})
    assert response.status_code == 422


def test_cost_permissions_unpriced_currency_totals_and_void_preserve_original(platform):
    owner = platform["login"]("owner-a")
    path = f"/internal/projects/{PROJECT}/costs"
    base = {"phase": "estimated", "category": "analysis", "minutes": 120, "note": "pending explicitly configured rate"}
    unpriced = post(owner, path, base)
    assert unpriced.status_code == 200, unpriced.text
    assert post(owner, path, {**base, "minutes": -1}).status_code == 422
    assert post(owner, path, {**base, "cost_minor": 500}).status_code == 422
    assert post(owner, path, {**base, "cost_minor": True, "currency": "TWD"}).status_code == 422
    twd = post(owner, path, {**base, "minutes": 60, "cost_minor": 50000, "currency": "TWD"}).json()
    assert post(owner, path, {**base, "phase": "actual", "minutes": 30, "cost_minor": 1000, "currency": "USD"}).status_code == 200
    result = owner.get(path).json()
    assert result["totals"]["estimated"] == {"minutes": 180, "amounts": [{"currency": "TWD", "cost_minor": 50000}], "unpriced_entries": 1, "cost_status": "unconfigured"}
    assert result["totals"]["actual"]["amounts"] == [{"currency": "USD", "cost_minor": 1000}]
    for profile in ("customer-a", "engineer-a", "reviewer-a"):
        client = platform["login"](profile)
        assert client.get("/internal/cost-projects").status_code == 403
        assert client.get(path).status_code == 403
        assert post(client, path, base).status_code == 403
        assert post(client, f"/internal/costs/{twd['id']}/void", {"reason": "unauthorized"}).status_code == 403
    finance = platform["login"]("finance-a")
    assert finance.get(path).status_code == 404
    assert finance.get("/internal/cost-projects").json()["items"] == []
    with platform["engine"].begin() as conn:
        add(conn, m.grants, TENANT, user_id=fixed("finance-a"), resource_id=PROJECT, reason="explicit synthetic financial project grant")
    assert finance.get(path).status_code == 200
    selected = finance.get("/internal/cost-projects").json()["items"]
    assert len(selected) == 1 and selected[0]["id"] == PROJECT and set(selected[0]) == {"id", "name", "year"}
    assert finance.get(f"/internal/projects/{PROJECT}").status_code == 403
    key = str(uuid4())
    voided = post(finance, f"/internal/costs/{twd['id']}/void", {"reason": "correct by adding a new entry"}, key)
    assert voided.status_code == 200 and voided.json()["cost_minor"] == 50000
    assert voided.json()["voided_at"] and voided.json()["void_reason"]
    assert post(finance, f"/internal/costs/{twd['id']}/void", {"reason": "correct by adding a new entry"}, key).json() == voided.json()
    assert finance.get(path).json()["totals"]["estimated"]["minutes"] == 120


def test_unconfigured_dispatch_blocks_new_confirmation_without_rewriting_existing_schedule(platform):
    owner = platform["login"]("owner-a")
    body = schedule()
    assert post(owner, f"/internal/batches/{BATCH}/schedule", body).status_code == 200
    with platform["engine"].begin() as conn:
        before = one(conn, m.batches, TENANT, m.batches.c.id == BATCH)
        slots = all_rows(conn, m.resource_slots, None, m.resource_slots.c.batch_id == BATCH)
        conn.execute(delete(e.dispatch_policies).where(e.dispatch_policies.c.tenant_id == TENANT))
    view = owner.get("/internal/dispatch").json()
    assert view["policy"]["status"] == "unconfigured" and view["travel_buffer_minutes"] is None
    response = post(owner, f"/internal/batches/{BATCH}/schedule", schedule())
    assert response.status_code == 409 and response.json()["detail"]["code"] == "DISPATCH_POLICY_UNCONFIGURED"
    with platform["engine"].connect() as conn:
        assert one(conn, m.batches, TENANT, m.batches.c.id == BATCH) == before
        assert all_rows(conn, m.resource_slots, None, m.resource_slots.c.batch_id == BATCH) == slots


def test_qualification_and_tool_configuration_requires_role_version_and_full_interval(platform):
    owner = platform["login"]("owner-a")
    engineer = platform["login"]("engineer-a")
    assert post(engineer, "/internal/dispatch/policy", {"expected_version": 1, "travel_buffer_minutes": 0, "reason": "no authority"}).status_code == 403
    policy = {"expected_version": 1, "travel_buffer_minutes": 0, "reason": "explicit no travel local session"}
    assert post(owner, "/internal/dispatch/policy", policy).status_code == 200
    assert post(owner, "/internal/dispatch/policy", policy).status_code == 409
    with platform["engine"].begin() as conn:
        qualification = one(conn, e.dispatch_qualifications, TENANT, e.dispatch_qualifications.c.user_id == fixed("owner-a"),
                            e.dispatch_qualifications.c.role == "reviewer", e.dispatch_qualifications.c.service_code == "VA")
    body = {"expected_version": 1, "user_id": fixed("owner-a"), "role": "reviewer", "service_code": "VA",
            "active": True, "valid_until": (m.now() + timedelta(days=1)).isoformat(), "reason": "explicit qualification expires before proposed work"}
    assert post(owner, "/internal/dispatch/qualifications", body).status_code == 200
    result = post(owner, f"/internal/batches/{BATCH}/schedule", schedule())
    assert result.json()["detail"]["code"] == "QUALIFICATION_UNCONFIGURED"
    assert post(owner, "/internal/dispatch/qualifications", {**body, "expected_version": 2, "valid_until": None}).status_code == 200
    result = post(owner, f"/internal/batches/{BATCH}/schedule", schedule(equipment="UNCONFIGURED"))
    assert result.json()["detail"]["code"] == "TOOL_UNCONFIGURED"
    with platform["engine"].begin() as conn:
        conn.execute(delete(e.dispatch_qualifications).where(e.dispatch_qualifications.c.user_id == fixed("owner-a")))
    person = next(row for row in owner.get("/internal/dispatch").json()["items"] if row["id"] == fixed("owner-a"))
    assert person["skills"] == [] and person["qualification_status"] == "unconfigured"
    assert qualification["service_code"] == "VA"


def test_tool_capacity_single_actor_reservation_and_safe_capacity_updates(platform):
    owner = platform["login"]("owner-a")
    tool = {"expected_version": 0, "name": "two-license-pool", "capacity": 2, "service_codes": ["VA", "WVA"], "active": True, "reason": "two explicitly purchased synthetic units"}
    created = post(owner, "/internal/dispatch/tools", tool)
    assert created.status_code == 200
    body = schedule(equipment=tool["name"], equipment_units=2)
    first = post(owner, f"/internal/batches/{BATCH}/schedule", body)
    assert first.status_code == 200 and first.json()["scheduling_checks"]["equipment_units"] == 2
    other_body = {**body, "engineer_id": fixed("engineer-a"), "reviewer_id": fixed("reviewer-a"), "equipment_units": 1}
    other_batch = fixed("batch-a-WVA")
    result = post(owner, f"/internal/batches/{other_batch}/schedule", other_body)
    assert result.status_code == 409 and result.json()["detail"]["code"] == "TOOL_CAPACITY_CONFLICT"
    with platform["engine"].connect() as conn:
        slots = all_rows(conn, m.resource_slots, None, m.resource_slots.c.batch_id == BATCH)
        assert len(slots) == 3 and len([row for row in slots if row["resource"].startswith("person:")]) == 1
    assert post(owner, f"/internal/batches/{BATCH}/schedule", {**body, "equipment_units": 1}).status_code == 200
    assert post(owner, f"/internal/batches/{other_batch}/schedule", other_body).status_code == 200
    for patch in ({"capacity": 1}, {"active": False}, {"service_codes": ["VA", "PT"]}):
        result = post(owner, "/internal/dispatch/tools", {**tool, "expected_version": 1, **patch})
        assert result.status_code == 409 and result.json()["detail"]["code"] == "TOOL_IN_USE"
    assert post(owner, "/internal/dispatch/tools", {**tool, "expected_version": 1, "capacity": 3}).status_code == 200


def test_person_conflicts_respect_cross_tenant_index_without_disclosure_and_buffer(platform):
    owner = platform["login"]("owner-a")
    body = schedule()
    start = datetime_from(body["start_at"])
    foreign_batch = str(uuid4())
    with platform["engine"].begin() as conn:
        add(conn, m.resource_slots, tenant_id=fixed("tenant-b"), batch_id=foreign_batch,
            resource=f"person:{fixed('owner-a')}", start_at=start - timedelta(hours=1), end_at=start - timedelta(minutes=10))
    result = post(owner, f"/internal/batches/{BATCH}/schedule", body)
    assert result.status_code == 409 and result.json()["detail"]["code"] == "SCHEDULE_CONFLICT"
    assert foreign_batch not in result.text and fixed("tenant-b") not in result.text
    assert post(owner, "/internal/dispatch/policy", {"expected_version": 1, "travel_buffer_minutes": 0, "reason": "explicit test zero buffer"}).status_code == 200
    assert post(owner, f"/internal/batches/{BATCH}/schedule", body).status_code == 200


def datetime_from(value):
    return datetime.fromisoformat(value)


def test_inactive_assignment_and_legacy_reservations_fail_closed(platform):
    owner = platform["login"]("owner-a")
    body = schedule(engineer_id=fixed("engineer-a"), reviewer_id=fixed("reviewer-a"))
    with platform["engine"].begin() as conn:
        change(conn, m.users, None, fixed("engineer-a"), active=False)
    assert post(owner, f"/internal/batches/{BATCH}/schedule", body).status_code == 422
    with platform["engine"].begin() as conn:
        change(conn, m.users, None, fixed("engineer-a"), active=True)
        add(conn, m.resource_slots, tenant_id=TENANT, batch_id=str(uuid4()), resource="equipment:test-kit",
            start_at=datetime_from(body["start_at"]), end_at=datetime_from(body["end_at"]))
    result = post(owner, f"/internal/batches/{BATCH}/schedule", body)
    assert result.json()["detail"]["code"] == "SCHEDULE_CONFLICT"


def test_synthetic_seed_preserves_explicit_policy_and_existing_tasks(platform):
    from kuanguard.project_execution import seed_synthetic_execution
    owner = platform["login"]("owner-a")
    assert post(owner, "/internal/dispatch/policy", {"expected_version": 1, "travel_buffer_minutes": 7, "reason": "explicit changed policy"}).status_code == 200
    with platform["engine"].begin() as conn:
        previous_tasks = all_rows(conn, m.tasks, TENANT)
        seed_synthetic_execution(conn)
        assert one(conn, e.dispatch_policies, TENANT)["travel_buffer_minutes"] == 7
        assert all_rows(conn, m.tasks, TENANT) == previous_tasks


def test_expired_project_grant_revokes_all_execution_views_and_writes(platform):
    owner = platform["login"]("owner-a")
    row = task(owner)
    with platform["engine"].begin() as conn:
        grant = one(conn, m.grants, TENANT, m.grants.c.user_id == fixed("owner-a"), m.grants.c.resource_id == PROJECT)
        change(conn, m.grants, TENANT, grant["id"], expires_at=m.now() - timedelta(seconds=1))
    for suffix in ("tasks", "decisions", "costs"):
        assert owner.get(f"/internal/projects/{PROJECT}/{suffix}").status_code == 404
    assert update_task(owner, row, title="revoked mutation").status_code == 404
    assert post(owner, f"/internal/projects/{PROJECT}/decisions", {
        "title": "revoked", "occurred_at": m.now().isoformat(), "internal_note": "private"}).status_code == 404
    assert post(owner, f"/internal/projects/{PROJECT}/costs", {
        "phase": "actual", "category": "analysis", "minutes": 10, "note": "revoked"}).status_code == 404


def test_timezone_normalization_preserves_instant_and_legacy_task_upgrade(platform):
    owner = platform["login"]("owner-a")
    due = "2026-10-01T09:00:00+08:00"
    created = task(owner, due_at=due)
    assert datetime_from(created["due_at"]).hour == 1
    legacy = next(row for row in owner.get(f"/internal/projects/{PROJECT}/tasks").json()["items"] if row["id"] != created["id"])
    changed = update_task(owner, legacy, customer_note="legacy content preserved", due_at=due)
    assert changed.status_code == 200 and changed.json()["id"] == legacy["id"] and changed.json()["version"] == 2
    decision = post(owner, f"/internal/projects/{PROJECT}/decisions", {
        "title": "offset timestamp", "occurred_at": due, "internal_note": "explicit time zone"})
    assert datetime_from(decision.json()["occurred_at"]).hour == 1
    taipei = timezone(timedelta(hours=8))
    start = (m.now() + timedelta(days=8)).astimezone(taipei)
    result = post(owner, f"/internal/batches/{BATCH}/schedule", schedule(
        start_at=start.isoformat(), end_at=(start + timedelta(hours=1)).isoformat()))
    assert result.status_code == 200
    observed = datetime_from(result.json()["start_at"])
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    assert observed == start


def test_bounded_task_links_and_legacy_costs_are_not_silently_reclassified(platform):
    owner = platform["login"]("owner-a")
    row = task(owner)
    assert post(owner, f"/internal/projects/{PROJECT}/tasks", {"title": "excess links", "dependency_ids": [str(uuid4()) for _ in range(21)]}).status_code == 422
    assert post(owner, f"/internal/projects/{PROJECT}/tasks", {"title": "duplicate links", "dependency_ids": [row["id"], row["id"]]}).status_code == 422
    assert post(owner, f"/internal/projects/{PROJECT}/decisions", {
        "title": "duplicate links", "occurred_at": m.now().isoformat(), "internal_note": "note", "task_ids": [row["id"], row["id"]]}).status_code == 422
    with platform["engine"].begin() as conn:
        legacy = add(conn, m.time_entries, TENANT, project_id=PROJECT, category="analysis", minutes=60,
                     cost_minor=50000, actor_id=fixed("owner-a"), note="legacy phase and currency were never captured")
    result = owner.get(f"/internal/projects/{PROJECT}/costs").json()
    assert result["legacy_status"] == "unclassified_excluded"
    assert result["legacy_entries"][0]["id"] == legacy["id"]
    assert result["totals"]["actual"]["minutes"] == 0 and result["totals"]["actual"]["cost_status"] == "unconfigured"


def test_margin_requires_active_contract_and_complete_same_currency_costs(platform):
    owner = platform["login"]("owner-a")
    path = f"/internal/projects/{PROJECT}/costs"
    margin = owner.get(path).json()["margin"]
    assert margin["contract_amount_minor"] is None and margin["estimated_reason"] == "no_active_contract"
    with platform["engine"].begin() as conn:
        quote = add(conn, m.quotes, TENANT, family_id=str(uuid4()), version=1, title="explicit synthetic contract basis",
                    amount_minor=120000, currency="TWD", services=["VA"], valid_until=m.now()+timedelta(days=10), status="accepted")
        contract = add(conn, m.contracts, TENANT, quote_id=quote["id"], title=quote["title"], amount_minor=120000,
                       status="active", services=["VA"])
        change(conn, m.projects, TENANT, PROJECT, contract_id=contract["id"])
    margin = owner.get(path).json()["margin"]
    assert margin["contract_amount_minor"] == 120000 and margin["actual_reason"] == "cost_not_entered"
    base = {"phase": "estimated", "category": "analysis", "minutes": 60, "cost_minor": 30000, "currency": "TWD", "note": "explicit total line cost"}
    assert post(owner, path, base).status_code == 200
    assert post(owner, path, {**base, "phase": "actual", "cost_minor": 150000}).status_code == 200
    margin = owner.get(path).json()["margin"]
    assert margin["estimated_cost_minor"] == 30000 and margin["estimated_gross_margin_minor"] == 90000
    assert margin["actual_cost_minor"] == 150000 and margin["actual_gross_margin_minor"] == -30000
    assert margin["estimated_reason"] is None and margin["actual_reason"] is None
    assert margin["basis"] == "合約金額減已登錄成本，非正式收入認列"
    mixed = post(owner, path, {**base, "currency": "USD"}).json()
    unpriced = post(owner, path, {**base, "phase": "actual", "cost_minor": None, "currency": None}).json()
    margin = owner.get(path).json()["margin"]
    assert margin["estimated_gross_margin_minor"] is None and margin["estimated_reason"] == "mixed_cost_currencies"
    assert margin["actual_cost_minor"] is None and margin["actual_reason"] == "unpriced_entries"
    for row in (mixed, unpriced):
        assert post(owner, f"/internal/costs/{row['id']}/void", {"reason": "correct synthetic entry"}).status_code == 200
    with platform["engine"].begin() as conn:
        change(conn, m.contracts, TENANT, contract["id"], status="cancelled")
    margin = owner.get(path).json()["margin"]
    assert margin["contract_amount_minor"] is None and margin["actual_reason"] == "no_active_contract"
    with platform["engine"].begin() as conn:
        change(conn, m.contracts, TENANT, contract["id"], status="active", amount_minor=120001)
    margin = owner.get(path).json()["margin"]
    assert margin["contract_reason"] == "contract_quote_amount_mismatch" and margin["estimated_cost_minor"] is None


def test_create_project_can_bind_only_active_same_tenant_accepted_contract(platform):
    owner = platform["login"]("owner-a")
    with platform["engine"].begin() as conn:
        quote = add(conn, m.quotes, TENANT, family_id=str(uuid4()), version=1, title="合成核定報價",
                    amount_minor=120000, currency="TWD", services=["VA"], status="accepted")
        contract = add(conn, m.contracts, TENANT, quote_id=quote["id"], title=quote["title"], amount_minor=120000,
                       services=["VA"], status="active")
        other_quote = add(conn, m.quotes, fixed("tenant-b"), family_id=str(uuid4()), version=1,
                          title="另一企業", amount_minor=100, services=["VA"], status="accepted")
        other = add(conn, m.contracts, fixed("tenant-b"), quote_id=other_quote["id"], title="另一企業",
                    amount_minor=100, services=["VA"], status="active")
    payload = {"name": "有核定合約的專案", "company_name": "合成企業", "year": 2026, "contract_id": contract["id"]}
    result = post(owner, "/internal/projects", payload)
    assert result.status_code == 200 and result.json()["contract_id"] == contract["id"]
    assert post(owner, "/internal/projects", {**payload, "contract_id": other["id"]}).status_code == 404
    with platform["engine"].begin() as conn:
        change(conn, m.contracts, TENANT, contract["id"], status="cancelled")
    assert post(owner, "/internal/projects", payload).status_code == 409
