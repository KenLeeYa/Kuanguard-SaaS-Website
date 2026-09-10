from datetime import timedelta
from uuid import uuid4

from kuanguard import models as m
from kuanguard.db import add, all_rows, change
from kuanguard.seed import fixed


def save(client, payload, version=0, kind="campaign"):
    return client.put(f"/app/drafts/{kind}/new", json={"expected_version": version, "payload": payload})


def test_draft_actor_tenant_version_and_expiry(platform):
    a, b, owner = platform["login"](), platform["login"]("customer-b"), platform["login"]("owner-a")
    path = "/app/drafts/campaign/new"
    response = save(a, {"name": "續接草稿"})
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 1
    assert b.get(path).status_code == 404
    assert owner.get(path).status_code in {403, 404}
    assert save(a, {"name": "另一視窗"}, 1).json()["version"] == 2
    assert save(a, {"name": "不得蓋掉新版"}, 1).status_code == 409
    assert a.delete(path + "?version=1").status_code == 409
    assert a.get(path).json()["payload"]["name"] == "另一視窗"
    assert save(a, {"recipients": ["forbidden@example.invalid"]}, 2).status_code == 422
    assert save(a, {"name": "x" * 5000}, 2).status_code == 422
    assert a.get(path + "?tenant_id=x").status_code == 422
    with platform["engine"].begin() as conn:
        row = all_rows(conn, m.form_drafts, fixed("tenant-a"))[0]
        change(conn, m.form_drafts, fixed("tenant-a"), row["id"], expires_at=m.now()-timedelta(seconds=1))
    assert a.get(path).status_code == 404
    assert save(a, {"name": "新草稿"}, 0).json()["version"] == 3
    assert a.delete(path + "?version=2").status_code == 409
    assert a.delete(path + "?version=3").status_code == 200
    assert a.get(path).status_code == 404


def test_draft_roles_csrf_payload_and_purchase_recovery(platform):
    customer, learner = platform["login"](), platform["login"]("learner-a")
    assert save(learner, {"name": "x"}).status_code == 403
    assert save(customer, {"points": True}, kind="purchase").status_code == 422
    assert save(customer, {"order_id": "x", "points": 100}, kind="purchase").status_code == 200
    assert save(customer, {"course_id": "x", "learner_id": "y", "cohort": "2026"}, kind="training").status_code == 200
    customer.headers["x-csrf-token"] = "wrong"
    assert save(customer, {"name": "x"}).status_code == 403


def test_order_detail_is_scoped_to_actor_and_tenant(platform):
    a, b = platform["login"](), platform["login"]("customer-b")
    with platform["engine"].begin() as conn:
        own = add(conn, m.orders, fixed("tenant-a"), actor_id=fixed("customer-a"), points=100, amount_minor=10000)
        other = add(conn, m.orders, fixed("tenant-a"), actor_id=fixed("learner-a"), points=100, amount_minor=10000)
    assert a.get(f"/customer/orders/{own['id']}").status_code == 200
    assert b.get(f"/customer/orders/{own['id']}").status_code == 404
    assert a.get(f"/customer/orders/{other['id']}").status_code == 404


def test_ticket_dialogue_internal_notes_and_closed_stale_replies(platform):
    a, b, pm = platform["login"](), platform["login"]("customer-b"), platform["login"]("pm-a")
    with platform["engine"].begin() as conn:
        ticket = add(conn, m.tickets, fixed("tenant-a"), actor_id=fixed("customer-a"), subject="支援", text="合成問題")
    public = f"/customer/tickets/{ticket['id']}"
    private = f"/internal/tickets/{ticket['id']}"
    def send(client, path, text, visibility="customer", key=None):
        return client.post(path + "/messages", json={"text": text, "visibility": visibility},
                           headers={"idempotency-key": key or str(uuid4())})
    assert send(b, public, "wrong tenant").status_code == 404
    assert send(a, public, "secret note", "internal").status_code == 403
    assert send(pm, private, "僅內部", "internal").status_code == 200
    key = str(uuid4())
    assert send(pm, private, "公開回覆", key=key).status_code == 200
    assert send(pm, private, "公開回覆", key=key).status_code == 200
    assert len(a.get(public).json()["messages"]) == 1
    assert len(pm.get(private).json()["messages"]) == 2
    assert a.get(public).json()["messages"][0]["text"] == "公開回覆"
    assert send(a, public, "補充說明").status_code == 200
    with platform["engine"].begin() as conn:
        change(conn, m.tickets, fixed("tenant-a"), ticket["id"], status="closed")
        assert len(all_rows(conn, m.notifications, fixed("tenant-a"), m.notifications.c.title == "工單已有回覆")) == 1
    assert send(a, public, "已關閉不可再送").status_code == 409
