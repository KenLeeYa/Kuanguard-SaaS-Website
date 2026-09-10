from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from . import models as m, wallet
from .catalog import SERVICES, COURSE, COURSE_LESSONS, COURSE_QUESTIONS
from .config import settings
from .db import add, one, set_tenant
from . import execution_models  # noqa: F401 -- register additive tables before create_all

PROFILES = {
    "owner-a": ("a", "示範單一管理者", ["portfolio_owner", "pm", "engineer", "reviewer", "finance"]),
    "customer-a": ("a", "示範企業 A・企業窗口", ["customer_admin", "customer_contact", "campaign_manager", "training_manager", "billing_manager"]),
    "engineer-a": ("a", "示範工程師", ["engineer"]),
    "reviewer-a": ("a", "示範覆核者", ["reviewer"]),
    "finance-a": ("a", "示範財務", ["finance"]),
    "pm-a": ("a", "示範專案經理", ["pm"]),
    "learner-a": ("a", "示範學員 A", ["learner"]),
    "learner-a2": ("a", "示範學員 A・業務部", ["learner"]),
    "customer-b": ("b", "示範企業 B・企業窗口", ["customer_admin", "customer_contact", "campaign_manager", "training_manager", "billing_manager"]),
    "learner-b": ("b", "示範學員 B", ["learner"]),
}


def fixed(label):
    return str(uuid5(NAMESPACE_URL, "kuanguard-development:" + label))


def seed(conn):
    if settings().app_env not in {"development", "test"}:
        raise RuntimeError("Development seed prohibited")
    if one(conn, m.tenants, None, m.tenants.c.id == fixed("tenant-a")):
        from .project_execution import seed_synthetic_execution
        seed_synthetic_execution(conn)
        return {"status": "already_seeded"}
    for service in SERVICES:
        add(conn, m.service_catalog, **service)
    course = add(conn, m.courses, id=fixed("course"), **COURSE)
    for index, (title, content, seconds) in enumerate(COURSE_LESSONS):
        add(conn, m.lessons, course_id=course["id"], title=title, content=content, position=index+1, min_seconds=seconds)
    for index, (prompt, choices, correct, explanation) in enumerate(COURSE_QUESTIONS):
        add(conn, m.questions, course_id=course["id"], prompt=prompt, choices=choices,
            correct_choice=correct, explanation=explanation, position=index+1)
    for suffix in ("a", "b"):
        tenant = add(conn, m.tenants, id=fixed(f"tenant-{suffix}"), name=f"示範企業 {suffix.upper()}（合成資料）", verified=True)
        set_tenant(conn, tenant["id"])
        for key, (profile_tenant, name, roles) in PROFILES.items():
            if profile_tenant != suffix:
                continue
            user = add(conn, m.users, id=fixed(key), name=name, email=f"{key}@example.invalid")
            for role in roles:
                add(conn, m.memberships, tenant_id=tenant["id"], user_id=user["id"], role=role,
                    department="業務部" if key == "learner-a2" else "資訊部")
        project = add(conn, m.projects, tenant["id"], id=fixed(f"project-{suffix}"),
                      name="2026 年度資安改善計畫", year=2026, company_name=tenant["name"])
        for key, (profile_tenant, _, roles) in PROFILES.items():
            if profile_tenant == suffix and set(roles).intersection({"customer_contact", "pm", "engineer", "reviewer"}):
                add(conn, m.grants, tenant["id"], user_id=fixed(key), resource_id=project["id"], reason="development fixture")
        for index, service in enumerate(SERVICES):
            package = add(conn, m.work_packages, tenant["id"], project_id=project["id"], service_code=service["code"], allowance=2)
            batch = add(conn, m.batches, tenant["id"], id=fixed(f"batch-{suffix}-{service['code']}"),
                        project_id=project["id"], package_id=package["id"], service_code=service["code"],
                        title=f"{service['name']}・第一批次", engineer_id=fixed("engineer-a") if suffix == "a" else None,
                        reviewer_id=fixed("reviewer-a") if suffix == "a" else None,
                        retest_deadline=m.now()+timedelta(days=90))
            if service["mode"] == "engineer":
                for asset in (["192.0.2.10", "192.0.2.20"] if service["code"] in {"VA", "SHC"} else
                              ["https://demo.example.invalid"] if service["code"] in {"WVA", "PT"} else ["src/example.py"]):
                    add(conn, m.scope_assets, tenant["id"], batch_id=batch["id"], asset=asset, version=1)
            entitlement = add(conn, m.entitlements, tenant["id"], project_id=project["id"], service_code=service["code"], quantity=2)
            add(conn, m.entitlement_ledger, tenant["id"], entitlement_id=entitlement["id"], kind="grant", quantity=2,
                business_key=f"seed:{entitlement['id']}", reason="合成年度服務額度")
            add(conn, m.tasks, tenant["id"], project_id=project["id"], batch_id=batch["id"], title=f"確認{service['name']}範圍",
                due_at=m.now()+timedelta(days=7+index))
        wallet.grant(conn, tenant["id"], 500, "paid_sandbox", amount_minor=50000)
        wallet.grant(conn, tenant["id"], 40, "gift", purpose="training", expires_at=m.now()+timedelta(days=30))
        for data_class, days in [("raw_evidence", 90), ("reports", 365), ("recipients", 90), ("audit", 365)]:
            add(conn, m.retention_policies, tenant["id"], data_class=data_class, days=days, version=1)
        add(conn, m.notifications, tenant["id"], user_id=fixed(f"customer-{suffix}"),
            title="示範環境已就緒", text="目前顯示合成資料；正式服務、寄送、金流及教材需完成啟用。")
    from .project_execution import seed_synthetic_execution
    seed_synthetic_execution(conn)
    return {"status": "seeded", "tenants": 2, "services": 7, "synthetic": True}


def seed_owner_increment(conn):
    """Add the v1.1 owner fixture without replacing any prior rows or financial state."""
    if settings().app_env not in {"development", "test"}:
        raise RuntimeError("Development fixture prohibited")
    tenant_id = fixed("tenant-a")
    set_tenant(conn, tenant_id)
    suffix, name, roles = PROFILES["owner-a"]
    if not one(conn, m.users, None, m.users.c.id == fixed("owner-a")):
        add(conn, m.users, id=fixed("owner-a"), name=name, email="owner-a@example.invalid")
    for role in roles:
        if not one(conn, m.memberships, None, m.memberships.c.user_id == fixed("owner-a"), m.memberships.c.tenant_id == tenant_id, m.memberships.c.role == role):
            add(conn, m.memberships, tenant_id=tenant_id, user_id=fixed("owner-a"), role=role, department="營運管理")
    if not one(conn, m.grants, tenant_id, m.grants.c.user_id == fixed("owner-a"), m.grants.c.resource_id == fixed("project-a")):
        add(conn, m.grants, tenant_id, user_id=fixed("owner-a"), resource_id=fixed("project-a"), reason="v1.1 explicit development project grant")
    return {"status": "owner_fixture_added_or_preserved", "original_data_preserved": True}
