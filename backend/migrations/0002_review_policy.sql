-- Additive v1.1 policy. Existing role assignments, results, ledger and jobs are preserved.
ALTER TABLE projects ADD COLUMN IF NOT EXISTS requires_independent_review BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS review_policy_reason TEXT DEFAULT 'single-owner standard policy';
-- Applied by scripts/migrate.py once and recorded in schema_revisions.
-- Rollback retains columns/data, reconfigures policy and redeploys the prior compatible application.
-- No destructive down migration.
