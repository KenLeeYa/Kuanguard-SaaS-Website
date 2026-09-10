"""Job failure/recovery tests use temporary databases and never render report files."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from threading import Barrier, Event

import pytest
from sqlalchemy import create_engine, text

from kuanguard import models as m, reports, wallet, worker
from kuanguard.db import add, all_rows, aware, change, one
from kuanguard.security import digest
from kuanguard.seed import fixed


@pytest.fixture
def clock(monkeypatch):
    current = [m.now()]
    monkeypatch.setattr(m, "now", lambda: current[0])
    return current


def report_job(platform, clock, attempts=0):
    tenant = fixed("tenant-a")
    batch = fixed("batch-a-VA")
    dataset = {"synthetic": True, "marker": "immutable test snapshot"}
    with platform["engine"].begin() as conn:
        change(conn, m.batches, tenant, batch, status="approved", reviewed_by=fixed("owner-a"))
        snapshot = add(conn, m.snapshots, tenant, batch_id=batch, version=1, dataset=dataset,
                       sha256=digest(json.dumps(dataset, ensure_ascii=False, sort_keys=True)))
        report = add(conn, m.report_jobs, tenant, batch_id=batch, snapshot_id=snapshot["id"])
        job = add(conn, m.jobs, tenant_id=tenant, kind="report", resource_id=report["id"],
                  available_at=clock[0], attempts=attempts)
    return job, report


def mail_job(platform, clock, *, message_status="planned", campaign_status="scheduled", job_status="queued",
             attempts=0, expires_in=timedelta(minutes=30)):
    tenant = fixed("tenant-a")
    with platform["engine"].begin() as conn:
        group = add(conn, m.recipient_groups, tenant, name="synthetic worker test", owner_id=fixed("customer-a"))
        recipient = add(conn, m.recipients, tenant, group_id=group["id"], email="worker@example.invalid")
        campaign = add(conn, m.campaigns, tenant, group_id=group["id"], owner_id=fixed("customer-a"),
                       name="synthetic worker test", status=campaign_status, scheduled_at=clock[0])
        message_id = m.uid()
        reservation = wallet.reserve(conn, tenant, "phishing", message_id, 1, clock[0]+expires_in)
        message = add(conn, m.message_plans, tenant, id=message_id, campaign_id=campaign["id"],
                      recipient_id=recipient["id"], reservation_id=reservation["id"], status=message_status)
        job = add(conn, m.jobs, tenant_id=tenant, kind="sandbox_mail", resource_id=message_id,
                  available_at=clock[0], status=job_status, attempts=attempts)
    return job, message, reservation, campaign


def stored(platform, table, row_id, tenant=None):
    with platform["engine"].connect() as conn:
        return one(conn, table, tenant, table.c.id == row_id)


@pytest.mark.parametrize("old_fails", [False, True])
def test_stale_report_attempt_cannot_replace_completed_success(platform, clock, monkeypatch, old_fails):
    queued, report = report_job(platform, clock)
    outputs = []

    def generate(dataset, output):
        outputs.append(str(output))
        assert dataset["marker"] == "immutable test snapshot"
        if len(outputs) == 1:
            clock[0] += timedelta(minutes=6)
            assert worker.process_once()["status"] == "processed"
            if old_fails:
                raise RuntimeError("stale attempt failed after replacement success")
            return {"marker": "stale"}
        return {"marker": "replacement"}

    monkeypatch.setattr(reports, "generate_bundle", generate)
    assert worker.process_once()["status"] == "stale_claim"
    finished = stored(platform, m.report_jobs, report["id"], fixed("tenant-a"))
    job = stored(platform, m.jobs, queued["id"])
    assert finished["status"] == job["status"] == "completed"
    assert finished["manifest"] == {"marker": "replacement"}
    assert finished["error"] is None and job["error_code"] is None
    assert job["attempts"] == 2 and job["claim_token"] is None
    assert outputs[0] != outputs[1]
    assert finished["output_key"].replace("/", "\\") in outputs[1].replace("/", "\\")
    assert not (platform["tmp"] / "objects").exists()


def test_lease_renewal_is_bound_to_claim_and_tenant_and_cannot_revive_expiry(platform, clock):
    queued, _ = report_job(platform, clock)
    claimed = worker.claim_job()
    assert claimed["claim_token"]
    clock[0] += timedelta(minutes=4)
    assert worker._renew_claim(claimed) is True
    assert worker._renew_claim({**claimed, "claim_token": m.uid()}) is False
    assert worker._renew_claim({**claimed, "tenant_id": fixed("tenant-b")}) is False
    clock[0] += timedelta(minutes=2)
    worker._recover_expired()
    assert stored(platform, m.jobs, queued["id"])["claim_token"] == claimed["claim_token"]
    clock[0] += timedelta(minutes=4)
    assert worker._renew_claim(claimed) is False
    worker._recover_expired()
    recovered = stored(platform, m.jobs, queued["id"])
    assert recovered["status"] == "queued" and recovered["claim_token"] is None
    replacement = worker.claim_job()
    assert replacement["claim_token"] != claimed["claim_token"]


def test_heartbeat_renews_during_long_generation_and_stops_on_exit(platform, clock, monkeypatch):
    queued, _ = report_job(platform, clock)
    claimed = worker.claim_job()
    clock[0] += timedelta(minutes=4)
    renewed = Event()
    original = worker._renew_claim

    def renew(job):
        result = original(job)
        renewed.set()
        return result

    monkeypatch.setattr(worker, "_renew_claim", renew)
    monkeypatch.setattr(worker, "HEARTBEAT_SECONDS", 0.01)
    with worker._lease_heartbeat(claimed):
        assert renewed.wait(timeout=2)
    row = stored(platform, m.jobs, queued["id"])
    assert aware(row["lease_until"]) == clock[0]+worker.LEASE_DURATION


def test_stale_recovery_scan_cannot_reset_a_replacement_claim(platform, clock, monkeypatch):
    queued, _ = report_job(platform, clock)
    original_claim = worker.claim_job()
    clock[0] += timedelta(minutes=6)
    replacement_token = m.uid()
    original_set = worker.set_tenant
    replaced = []

    def another_worker_won(conn, tenant, mutation=False):
        original_set(conn, tenant, mutation)
        if not replaced:
            replaced.append(True)
            change(conn, m.jobs, tenant, queued["id"], claim_token=replacement_token,
                   lease_until=clock[0]+worker.LEASE_DURATION, attempts=2)

    monkeypatch.setattr(worker, "set_tenant", another_worker_won)
    worker._recover_expired()
    current = stored(platform, m.jobs, queued["id"])
    assert current["status"] == "running" and current["claim_token"] == replacement_token
    assert current["claim_token"] != original_claim["claim_token"]


def test_two_workers_claim_one_job_once(platform, clock, monkeypatch):
    queued, _ = report_job(platform, clock)
    barrier = Barrier(2)
    original = worker.set_tenant

    def simultaneous_claim(conn, tenant, mutation=False):
        original(conn, tenant, mutation)
        barrier.wait(timeout=5)

    monkeypatch.setattr(worker, "set_tenant", simultaneous_claim)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker.claim_job(), range(2)))
    winners = [result for result in results if result]
    assert len(winners) == 1 and winners[0]["id"] == queued["id"]
    assert stored(platform, m.jobs, queued["id"])["attempts"] == 1


def test_queued_mail_expired_during_downtime_is_never_sent_and_releases_points(platform, clock):
    queued, message, reservation, _ = mail_job(platform, clock)
    clock[0] += timedelta(hours=1)
    assert worker.process_once() is None
    assert stored(platform, m.jobs, queued["id"])["status"] == "cancelled"
    assert stored(platform, m.message_plans, message["id"], fixed("tenant-a"))["status"] == "cancelled"
    assert stored(platform, m.reservations, reservation["id"], fixed("tenant-a"))["status"] == "released"
    with platform["engine"].connect() as conn:
        balance = wallet.summary(conn, fixed("tenant-a"))
        assert balance["available"] == 540 and balance["reserved"] == balance["consumed"] == 0
        assert all_rows(conn, m.raw_events, fixed("tenant-a")) == []


def test_mail_expiring_after_claim_is_not_sent(platform, clock, monkeypatch):
    queued, _, reservation, _ = mail_job(platform, clock, expires_in=timedelta(minutes=1))
    original = worker.claim_job

    def delayed_start():
        claim = original()
        clock[0] += timedelta(minutes=2)
        return claim

    monkeypatch.setattr(worker, "claim_job", delayed_start)
    assert worker.process_once()["status"] == "processed"
    assert stored(platform, m.jobs, queued["id"])["status"] == "cancelled"
    assert stored(platform, m.reservations, reservation["id"], fixed("tenant-a"))["status"] == "released"
    with platform["engine"].connect() as conn:
        assert wallet.summary(conn, fixed("tenant-a"))["consumed"] == 0


def test_paused_job_waits_without_using_attempts_then_resumes_once(platform, clock):
    queued, _, _, campaign = mail_job(platform, clock, campaign_status="paused")
    for _ in range(5):
        assert worker.claim_job() is None
    row = stored(platform, m.jobs, queued["id"])
    assert row["status"] == "paused" and row["attempts"] == 0 and row["claim_token"] is None
    with platform["engine"].begin() as conn:
        change(conn, m.campaigns, fixed("tenant-a"), campaign["id"], status="scheduled")
        change(conn, m.jobs, fixed("tenant-a"), queued["id"], status="queued")
    assert worker.process_once()["status"] == "processed"
    row = stored(platform, m.jobs, queued["id"])
    assert row["status"] == "completed" and row["attempts"] == 1
    with platform["engine"].connect() as conn:
        assert wallet.summary(conn, fixed("tenant-a"))["consumed"] == 1


def test_retry_limit_releases_confirmed_unsent_mail(platform, clock):
    queued, message, reservation, _ = mail_job(platform, clock, attempts=3)
    assert worker.claim_job() is None
    row = stored(platform, m.jobs, queued["id"])
    assert row["status"] == "dead_letter" and row["attempts"] == 3 and row["error_code"] == "RETRY_LIMIT"
    assert stored(platform, m.message_plans, message["id"], fixed("tenant-a"))["status"] == "cancelled"
    assert stored(platform, m.reservations, reservation["id"], fixed("tenant-a"))["status"] == "released"


def test_report_retry_limit_keeps_report_failure_visible(platform, clock, monkeypatch):
    queued, report = report_job(platform, clock, attempts=3)
    monkeypatch.setattr(reports, "generate_bundle", lambda *_: pytest.fail("retry limit must prevent rendering"))
    assert worker.process_once() is None
    assert stored(platform, m.jobs, queued["id"])["status"] == "dead_letter"
    assert stored(platform, m.report_jobs, report["id"], fixed("tenant-a"))["error"] == "RETRY_LIMIT"


def test_current_report_failure_is_recorded_without_sensitive_exception_text(platform, clock, monkeypatch):
    queued, report = report_job(platform, clock)

    def fail_generation(*_):
        raise RuntimeError("private evidence must never appear in the error receipt")

    monkeypatch.setattr(reports, "generate_bundle", fail_generation)
    assert worker.process_once()["error_code"] == "RuntimeError"
    job = stored(platform, m.jobs, queued["id"])
    result = stored(platform, m.report_jobs, report["id"], fixed("tenant-a"))
    assert job["status"] == result["status"] == "failed"
    assert job["claim_token"] is None and result["error"] == "RuntimeError"


def test_sandbox_failure_before_acceptance_releases_only_unsent_points(platform, clock, monkeypatch):
    queued, message, reservation, _ = mail_job(platform, clock)

    def fail_dispatch(*_):
        raise RuntimeError("synthetic pre-acceptance failure")

    monkeypatch.setattr(worker, "settle_message", fail_dispatch)
    assert worker.process_once()["status"] == "failed"
    assert stored(platform, m.jobs, queued["id"])["status"] == "failed"
    assert stored(platform, m.message_plans, message["id"], fixed("tenant-a"))["status"] == "cancelled"
    assert stored(platform, m.reservations, reservation["id"], fixed("tenant-a"))["status"] == "released"


def test_additive_claim_migration_preserves_legacy_jobs_and_replays(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'legacy-schema.db'}"
    monkeypatch.setenv("MIGRATION_DATABASE_URL", url)
    db = create_engine(url)
    with db.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE schema_revisions (version VARCHAR(60) PRIMARY KEY)")
        conn.execute(text("INSERT INTO schema_revisions(version) VALUES (:version)"), [
            {"version": version} for version in ["0001_initial", "0002_review_policy", "0003_portfolio_projection", "0004_retest_verification"]])
        conn.exec_driver_sql("CREATE TABLE jobs (id VARCHAR(36) PRIMARY KEY, status TEXT, attempts INTEGER)")
        conn.exec_driver_sql("INSERT INTO jobs(id,status,attempts) VALUES ('preserved-job','needs_review',2)")
    from scripts.migrate import migrate
    migrate()
    migrate()
    with db.connect() as conn:
        assert tuple(conn.execute(text("SELECT id,status,attempts,claim_token FROM jobs")).one()) == (
            "preserved-job", "needs_review", 2, None)
        assert conn.execute(text("SELECT count(*) FROM schema_revisions WHERE version='0005_worker_claim_token'")).scalar_one() == 1
    db.dispose()


@pytest.mark.parametrize("message_status", ["planned", "unknown", "in_flight"])
@pytest.mark.parametrize("legacy_claim", [False, True])
def test_uncertain_expired_mail_never_resends_or_releases(platform, clock, message_status, legacy_claim):
    queued, message, reservation, _ = mail_job(platform, clock, message_status=message_status)
    with platform["engine"].begin() as conn:
        change(conn, m.jobs, fixed("tenant-a"), queued["id"], status="running",
               claim_token=None if legacy_claim else m.uid(), lease_until=clock[0]+worker.LEASE_DURATION)
    clock[0] += timedelta(hours=1)
    assert worker.process_once() is None
    worker.expire_training()
    assert stored(platform, m.jobs, queued["id"])["status"] == "needs_review"
    assert stored(platform, m.message_plans, message["id"], fixed("tenant-a"))["status"] == "unknown"
    assert stored(platform, m.reservations, reservation["id"], fixed("tenant-a"))["status"] == "reserved"
    with platform["engine"].connect() as conn:
        balance = wallet.summary(conn, fixed("tenant-a"))
        assert balance["reserved"] == 1 and balance["consumed"] == 0


@pytest.mark.parametrize("initial_status", ["queued", "paused", "failed", "dead_letter"])
def test_housekeeping_releases_unsent_expiry_from_each_terminal_path(platform, clock, initial_status):
    queued, _, reservation, _ = mail_job(platform, clock, job_status=initial_status)
    clock[0] += timedelta(hours=1)
    worker.expire_training()
    worker.expire_training()
    assert stored(platform, m.jobs, queued["id"])["status"] == "cancelled"
    assert stored(platform, m.reservations, reservation["id"], fixed("tenant-a"))["status"] == "released"
    with platform["engine"].connect() as conn:
        releases = all_rows(conn, m.wallet_transactions, fixed("tenant-a"),
                            m.wallet_transactions.c.reservation_id == reservation["id"],
                            m.wallet_transactions.c.kind == "release")
        assert len(releases) == 1
