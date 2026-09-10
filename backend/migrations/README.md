# Database revisions

`uv run python scripts/migrate.py` applies `0001_initial` once, with composite tenant foreign keys,
PostgreSQL FORCE RLS and append-only triggers. `0001_initial.sql` is the generated immutable schema receipt.
Only the migration owner connects through `MIGRATION_DATABASE_URL`; API/worker use the non-owner
`kuanguard` role with NOBYPASSRLS. Credentials stay in ignored development `.env` / production secret manager.

Rollback is a verified database-and-object restore from the backup made before migration, into a new
isolated database first, followed by a connection switch. Never drop tables to simulate rollback.
Future schema changes must add a numbered revision and verify upgrade plus restore; editing the model
alone does not alter existing installations.

Incremental revisions preserve existing rows and completed jobs:

- `0002_review_policy`: explicit single-actor/contract independent review policy.
- `0003_portfolio_projection`: bounded tenant-scoped portfolio cache.
- `0004_retest_verification`: verified retest evidence.
- `0005_worker_claim_token`: stale-worker fencing.
- `0006_service_ledger_immutable`: append-only service units.
- `0007_drafts_tickets`: actor-scoped expiring drafts and ticket messages.
- `0008_training_rights`: immutable finite included/gift/manual seats and usage ledger.
- `0009_project_execution`: task sidecars/dependencies, meeting decisions, costs and explicit dispatch resources.
- `0010_tenant_lifecycle`: reviewed offboarding plans and privileged erasure receipts (no runtime grants on receipts).

Revisions 0009 and 0010 are independent additions; a deployment may have received 0010 first while the
execution module was still under test. Applying the remaining numbered revision is idempotent and does
not rewrite either schema or pre-existing business rows. Runtime always receives all applicable revisions
before the new handlers are enabled. Tests exercise the same numbered migration path against PostgreSQL.
