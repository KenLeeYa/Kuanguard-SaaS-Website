"""KUANGUARD durable jobs. Redis is a wake-up hint; database IDs determine tenant and scope."""
from datetime import timedelta
from contextlib import contextmanager
import argparse
import json
from threading import Event, Thread
import time

from sqlalchemy import select

from . import models as m, wallet
from .config import settings
from .db import add, all_rows, aware, change, engine, one, set_tenant
from .security import digest

LEASE_DURATION = timedelta(minutes=5)
HEARTBEAT_SECONDS = 60


def _claim_conditions(job):
    return (m.jobs.c.id == job["id"], m.jobs.c.tenant_id == job["tenant_id"],
            m.jobs.c.kind == job["kind"], m.jobs.c.resource_id == job["resource_id"],
            m.jobs.c.status == "running", m.jobs.c.claim_token == job.get("claim_token"))


def _renew_current(conn, job):
    current = m.now()
    return conn.execute(m.jobs.update().where(*_claim_conditions(job), m.jobs.c.lease_until > current)
                        .values(lease_until=current+LEASE_DURATION)).rowcount == 1


def _finish_claim(conn, job, status, **values):
    # The conditional write is also the SQLite writer lock, before any dependent changes.
    return conn.execute(m.jobs.update().where(*_claim_conditions(job), m.jobs.c.lease_until > m.now())
                        .values(status=status, claim_token=None, lease_until=None, **values)).rowcount == 1


def _renew_claim(job):
    with engine().begin() as conn:
        set_tenant(conn, job["tenant_id"], mutation=True)
        return _renew_current(conn, job)


@contextmanager
def _lease_heartbeat(job):
    stopped = Event()

    def renew():
        while not stopped.wait(HEARTBEAT_SECONDS):
            try:
                if not _renew_claim(job):
                    return
            except Exception:
                # A lost database connection must not grant ownership beyond the last lease.
                return

    thread = Thread(target=renew, daemon=True, name="kuanguard-report-lease")
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=1)


def _cancel_unsent(conn, tenant, message, reason, error_code, job_status="cancelled"):
    if not message or message["status"] != "planned":
        return False
    wallet.release(conn, tenant, message["reservation_id"], reason)
    change(conn, m.message_plans, tenant, message["id"], status="cancelled")
    conn.execute(m.jobs.update().where(m.jobs.c.tenant_id == tenant, m.jobs.c.kind == "sandbox_mail",
                                       m.jobs.c.resource_id == message["id"],
                                       m.jobs.c.status.in_(["queued", "paused", "running", "failed", "dead_letter"]))
                 .values(status=job_status, error_code=error_code, claim_token=None, lease_until=None))
    add(conn, m.audit_events, tenant, actor_id="worker", action="mail.not_sent", resource_id=message["id"], summary=reason)
    return True


def settle_message(conn, tenant, message_id, outcome, event_time=None):
    message = one(conn, m.message_plans, tenant, m.message_plans.c.id == message_id)
    if not message or message["status"] in {"accepted", "bounced", "cancelled", "rejected"}:
        return message
    if message["status"] == "unknown":
        return message  # Unknown state requires an explicit reconciliation decision; never blind resend.
    campaign = one(conn, m.campaigns, tenant, m.campaigns.c.id == message["campaign_id"])
    if not campaign or campaign["status"] in {"paused", "cancelled"}:
        return message
    if outcome == "accepted":
        occurred = event_time or m.now()
        wallet.consume(conn, tenant, message["reservation_id"], occurred_at=occurred)
        change(conn, m.message_plans, tenant, message_id, status="accepted", provider_ref=f"sandbox:{message_id}", accepted_at=occurred)
        add(conn, m.raw_events, tenant, campaign_id=campaign["id"], message_id=message_id, event_type="provider_accepted",
            provider_event_id=f"sandbox-accepted:{message_id}", occurred_at=occurred, classification="provider_evidence")
    elif outcome == "rejected":
        wallet.release(conn, tenant, message["reservation_id"], "sandbox provider confirmed not accepted")
        change(conn, m.message_plans, tenant, message_id, status="rejected", provider_ref=f"sandbox:{message_id}")
    else:
        change(conn, m.message_plans, tenant, message_id, status="unknown", provider_ref=f"sandbox-unknown:{message_id}")
    for job in all_rows(conn, m.jobs, None, m.jobs.c.tenant_id == tenant, m.jobs.c.kind == "sandbox_mail", m.jobs.c.resource_id == message_id):
        change(conn, m.jobs, tenant, job["id"], status="needs_review" if outcome == "unknown" else "completed", lease_until=None, claim_token=None)
    return one(conn, m.message_plans, tenant, m.message_plans.c.id == message_id)


def reconcile_message(conn, tenant, message_id, outcome, provider_reference, occurred_at, reason, actor_id):
    message = one(conn, m.message_plans, tenant, m.message_plans.c.id == message_id)
    if not message or message["status"] != "unknown":
        raise ValueError("MESSAGE_NOT_UNKNOWN")
    if not provider_reference or not reason:
        raise ValueError("RECONCILIATION_EVIDENCE_REQUIRED")
    if outcome == "accepted":
        wallet.consume(conn, tenant, message["reservation_id"], occurred_at=occurred_at)
        change(conn, m.message_plans, tenant, message_id, status="accepted", accepted_at=occurred_at, provider_ref=provider_reference)
    elif outcome == "rejected":
        wallet.release(conn, tenant, message["reservation_id"], reason)
        change(conn, m.message_plans, tenant, message_id, status="rejected", provider_ref=provider_reference)
    else:
        raise ValueError("CONFIRMED_RESULT_REQUIRED")
    add(conn, m.audit_events, tenant, actor_id=actor_id, action="mail.reconcile", resource_id=message_id,
        summary=f"{outcome}; reference={provider_reference}; reason={reason}")
    for job in all_rows(conn, m.jobs, None, m.jobs.c.tenant_id == tenant, m.jobs.c.kind == "sandbox_mail", m.jobs.c.resource_id == message_id):
        change(conn, m.jobs, tenant, job["id"], status="completed", lease_until=None, claim_token=None)
    return one(conn, m.message_plans, tenant, m.message_plans.c.id == message_id)


def _recover_expired():
    with engine().connect() as conn:
        expired_jobs = [dict(row) for row in conn.execute(select(m.jobs).where(
            m.jobs.c.kind.in_(["report", "sandbox_mail"]), m.jobs.c.status == "running", m.jobs.c.lease_until <= m.now())
            .order_by(m.jobs.c.created_at).limit(100)).mappings()]
    for expired in expired_jobs:
        with engine().begin() as conn:
            # One tenant lock per transaction, always acquired before a job row lock.
            set_tenant(conn, expired["tenant_id"], mutation=True)
            status = "queued" if expired["kind"] == "report" else "needs_review"
            recovered = conn.execute(m.jobs.update().where(*_claim_conditions(expired), m.jobs.c.lease_until <= m.now())
                                     .values(status=status, claim_token=None, lease_until=None)).rowcount
            if not recovered:
                continue
            if expired["kind"] == "sandbox_mail":
                message = one(conn, m.message_plans, expired["tenant_id"], m.message_plans.c.id == expired["resource_id"])
                if message and message["status"] in {"planned", "in_flight"}:
                    change(conn, m.message_plans, expired["tenant_id"], message["id"], status="unknown")
                elif message and message["status"] in {"accepted", "bounced", "cancelled", "rejected"}:
                    change(conn, m.jobs, expired["tenant_id"], expired["id"], status="completed")
            else:
                change(conn, m.report_jobs, expired["tenant_id"], expired["resource_id"], status="queued")


def claim_job():
    _recover_expired()
    with engine().connect() as conn:
        candidates = [dict(row) for row in conn.execute(select(m.jobs).where(
            m.jobs.c.status == "queued", m.jobs.c.kind.in_(["report", "sandbox_mail"]), m.jobs.c.available_at <= m.now())
            .order_by(m.jobs.c.created_at).limit(100)).mappings()]
    for candidate in candidates:
        with engine().begin() as conn:
            set_tenant(conn, candidate["tenant_id"], mutation=True)
            candidate_conditions = (
                m.jobs.c.id == candidate["id"], m.jobs.c.tenant_id == candidate["tenant_id"], m.jobs.c.status == "queued",
                m.jobs.c.kind == candidate["kind"], m.jobs.c.resource_id == candidate["resource_id"],
                m.jobs.c.attempts == candidate["attempts"], m.jobs.c.claim_token == candidate.get("claim_token"),
                m.jobs.c.available_at <= m.now())
            tenant = one(conn, m.tenants, None, m.tenants.c.id == candidate["tenant_id"], m.tenants.c.status == "active")
            if not tenant:
                cancelled = conn.execute(m.jobs.update().where(*candidate_conditions).values(
                    status="cancelled", error_code="TENANT_INACTIVE", claim_token=None, lease_until=None)).rowcount
                if cancelled and candidate["kind"] == "report":
                    change(conn, m.report_jobs, candidate["tenant_id"], candidate["resource_id"], status="cancelled", error="TENANT_INACTIVE")
                elif cancelled:
                    message = one(conn, m.message_plans, candidate["tenant_id"], m.message_plans.c.id == candidate["resource_id"])
                    _cancel_unsent(conn, candidate["tenant_id"], message, "tenant inactive before dispatch", "TENANT_INACTIVE")
                continue
            row = conn.execute(m.jobs.update().where(*candidate_conditions).values(status="running", claim_token=m.uid(),
                    attempts=candidate["attempts"]+1, lease_until=m.now()+LEASE_DURATION, error_code=None)
                .returning(*m.jobs.c)).mappings().first()
            if not row:
                continue
            job = dict(row)
            if job["kind"] == "sandbox_mail":
                message = one(conn, m.message_plans, job["tenant_id"], m.message_plans.c.id == job["resource_id"])
                campaign = one(conn, m.campaigns, job["tenant_id"], m.campaigns.c.id == message["campaign_id"]) if message else None
                if not message or not campaign:
                    _finish_claim(conn, job, "dead_letter", error_code="JOB_RESOURCE_SCOPE_MISMATCH")
                    continue
                reservation = one(conn, m.reservations, job["tenant_id"], m.reservations.c.id == message["reservation_id"])
                if message["status"] == "planned" and (campaign["status"] == "cancelled" or (reservation and aware(reservation["expires_at"]) <= m.now())):
                    _cancel_unsent(conn, job["tenant_id"], message, "dispatch cancelled or reservation expired before sending", "SEND_WINDOW_EXPIRED")
                    continue
                if message["status"] in {"unknown", "in_flight"}:
                    change(conn, m.message_plans, job["tenant_id"], message["id"], status="unknown")
                    _finish_claim(conn, job, "needs_review")
                    continue
                if message["status"] in {"accepted", "bounced", "cancelled", "rejected"}:
                    _finish_claim(conn, job, "completed")
                    continue
                if campaign["status"] == "paused":
                    _finish_claim(conn, job, "paused", attempts=candidate["attempts"])
                    continue
            if candidate["attempts"] >= 3:
                _finish_claim(conn, job, "dead_letter", attempts=candidate["attempts"], error_code="RETRY_LIMIT")
                if job["kind"] == "sandbox_mail":
                    _cancel_unsent(conn, job["tenant_id"], message, "retry limit reached before sending", "RETRY_LIMIT", "dead_letter")
                else:
                    change(conn, m.report_jobs, job["tenant_id"], job["resource_id"], status="failed", error="RETRY_LIMIT")
                continue
            return job
    return None


def process_once():
    job = claim_job()
    if not job:
        return None
    stale = {"id": job["id"], "kind": job["kind"], "status": "stale_claim"}
    try:
        if job["kind"] == "report":
            from .reports import generate_bundle
            with engine().begin() as conn:
                set_tenant(conn, job["tenant_id"], mutation=True)
                if not _renew_current(conn, job):
                    return stale
                report = one(conn, m.report_jobs, job["tenant_id"], m.report_jobs.c.id == job["resource_id"])
                if not report:
                    raise ValueError("JOB_RESOURCE_SCOPE_MISMATCH")
                snapshot = one(conn, m.snapshots, job["tenant_id"], m.snapshots.c.id == report["snapshot_id"])
                batch = one(conn, m.batches, job["tenant_id"], m.batches.c.id == report["batch_id"])
                if not snapshot or not batch or not batch["reviewed_by"] or snapshot["batch_id"] != batch["id"]:
                    raise ValueError("UNAPPROVED_JOB_RESOURCE")
                if digest(json.dumps(snapshot["dataset"], ensure_ascii=False, sort_keys=True)) != snapshot["sha256"]:
                    raise ValueError("SNAPSHOT_HASH_MISMATCH")
                dataset = snapshot["dataset"]
                change(conn, m.report_jobs, job["tenant_id"], report["id"], status="running")
            output_key = f"{job['tenant_id']}/reports/{report['id']}/claim-{job['claim_token']}"
            with _lease_heartbeat(job):
                manifest = generate_bundle(dataset, settings().local_data_dir / output_key)
            with engine().begin() as conn:
                set_tenant(conn, job["tenant_id"], mutation=True)
                if not _finish_claim(conn, job, "completed", error_code=None):
                    return stale
                change(conn, m.report_jobs, job["tenant_id"], report["id"], status="completed", manifest=manifest, output_key=output_key, error=None)
        else:
            if settings().app_env not in {"development", "test"}:
                raise ValueError("SANDBOX_MAIL_PROHIBITED")
            with engine().begin() as conn:
                set_tenant(conn, job["tenant_id"], mutation=True)
                if not _renew_current(conn, job):
                    return stale
                message = one(conn, m.message_plans, job["tenant_id"], m.message_plans.c.id == job["resource_id"])
                if not message:
                    raise ValueError("JOB_RESOURCE_SCOPE_MISMATCH")
                campaign = one(conn, m.campaigns, job["tenant_id"], m.campaigns.c.id == message["campaign_id"])
                if not campaign:
                    raise ValueError("JOB_RESOURCE_SCOPE_MISMATCH")
                reservation = one(conn, m.reservations, job["tenant_id"], m.reservations.c.id == message["reservation_id"])
                if message["status"] == "planned" and (campaign["status"] == "cancelled" or (reservation and aware(reservation["expires_at"]) <= m.now())):
                    _cancel_unsent(conn, job["tenant_id"], message, "reservation expired or campaign cancelled before sending", "SEND_WINDOW_EXPIRED")
                elif message["status"] in {"accepted", "bounced", "cancelled", "rejected", "unknown", "in_flight"}:
                    if message["status"] == "in_flight":
                        change(conn, m.message_plans, job["tenant_id"], message["id"], status="unknown")
                    _finish_claim(conn, job, "needs_review" if message["status"] in {"unknown", "in_flight"} else "completed")
                elif campaign["status"] == "paused":
                    _finish_claim(conn, job, "paused", attempts=max(0, job["attempts"]-1))
                else:
                    settle_message(conn, job["tenant_id"], message["id"], "accepted")
        return {"id": job["id"], "kind": job["kind"], "status": "processed"}
    except Exception as exc:
        error = type(exc).__name__  # Never log evidence, recipient names, raw payloads or credentials.
        with engine().begin() as conn:
            set_tenant(conn, job["tenant_id"], mutation=True)
            if not _finish_claim(conn, job, "failed", error_code=error):
                return stale
            if job["kind"] == "report":
                change(conn, m.report_jobs, job["tenant_id"], job["resource_id"], status="failed", error=error)
            else:
                message = one(conn, m.message_plans, job["tenant_id"], m.message_plans.c.id == job["resource_id"])
                _cancel_unsent(conn, job["tenant_id"], message, "sandbox dispatch failed before acceptance", error, "failed")
        return {"id": job["id"], "kind": job["kind"], "status": "failed", "error_code": error}


def expire_training():
    # Enumerate only tenant identities; individual work is re-scoped within its own transaction.
    with engine().connect() as conn:
        tenants = all_rows(conn, m.tenants, None, m.tenants.c.status == "active")
    for tenant in tenants:
        with engine().begin() as conn:
            set_tenant(conn, tenant["id"], mutation=True)
            from .portfolio import prune_expired_projections
            from .learning_entitlements import expire_authorizations
            prune_expired_projections(conn, tenant["id"], m.now())
            conn.execute(m.form_drafts.delete().where(m.form_drafts.c.tenant_id == tenant["id"],
                                                    m.form_drafts.c.expires_at <= m.now()))
            wallet.expire_lots(conn, tenant["id"])
            for message in all_rows(conn, m.message_plans, tenant["id"], m.message_plans.c.status == "planned"):
                reservation = one(conn, m.reservations, tenant["id"], m.reservations.c.id == message["reservation_id"])
                if reservation and aware(reservation["expires_at"]) <= m.now():
                    _cancel_unsent(conn, tenant["id"], message, "unsent message reservation expired", "SEND_WINDOW_EXPIRED")
            expire_authorizations(conn, tenant["id"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.once:
        print(json.dumps(process_once(), ensure_ascii=False))
        return
    last_expire = 0
    while True:
        result = process_once()
        if result:
            print(json.dumps(result), flush=True)
        if time.monotonic()-last_expire > 60:
            expire_training()
            last_expire = time.monotonic()
        if not result:
            time.sleep(2)


if __name__ == "__main__":
    main()
