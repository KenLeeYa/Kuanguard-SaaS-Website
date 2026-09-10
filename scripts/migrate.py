"""Versioned initial schema, scoped application role and PostgreSQL policies."""
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.schema import CreateTable, CreateIndex

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / ".env")
from kuanguard import models as m  # noqa: E402
from kuanguard.execution_models import EXECUTION_TABLES  # noqa: E402


def migrate():
    url = os.environ.get("MIGRATION_DATABASE_URL", os.environ.get("DATABASE_URL", "sqlite:///.local/kuanguard.db"))
    db = create_engine(url)
    with db.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_revisions (version VARCHAR(60) PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
        applied = conn.execute(text("SELECT version FROM schema_revisions WHERE version='0001_initial'")).first()
        if not applied:
            frozen_schema = ROOT / "backend" / "migrations" / "0001_initial.sql"
            if frozen_schema.exists() and conn.dialect.name == "postgresql":
                for statement in frozen_schema.read_text(encoding="utf-8").split(";"):
                    if statement.strip():
                        conn.exec_driver_sql(statement)
            else:
                m.metadata.create_all(conn)
            if conn.dialect.name == "postgresql":
                for name in m.TENANT_TABLES:
                    from sqlalchemy import inspect
                    if not inspect(conn).has_table(name):
                        continue  # Later additive revisions install their own policies.
                    conn.exec_driver_sql(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY')
                    conn.exec_driver_sql(f'ALTER TABLE "{name}" FORCE ROW LEVEL SECURITY')
                    conn.exec_driver_sql(f'''CREATE POLICY tenant_isolation ON "{name}"
                        USING (tenant_id = current_setting('app.tenant_id', true))
                        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))''')
                conn.exec_driver_sql("""CREATE FUNCTION deny_immutable_change() RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN RAISE EXCEPTION 'immutable record: append a correction'; END; $$""")
                for name in ["wallet_transactions", "snapshots", "publications", "audit_events", "schedule_history", "attempts"]:
                    conn.exec_driver_sql(f'''CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON "{name}"
                        FOR EACH ROW EXECUTE FUNCTION deny_immutable_change()''')
            conn.execute(text("INSERT INTO schema_revisions(version) VALUES ('0001_initial')"))
        if not conn.execute(text("SELECT version FROM schema_revisions WHERE version='0002_review_policy'")).first():
            from sqlalchemy import inspect
            existing_columns = {column["name"] for column in inspect(conn).get_columns("projects")}
            if "requires_independent_review" not in existing_columns:
                conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN requires_independent_review BOOLEAN NOT NULL DEFAULT false")
            if "review_policy_reason" not in existing_columns:
                conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN review_policy_reason TEXT DEFAULT 'single-owner standard policy'")
            conn.execute(text("INSERT INTO schema_revisions(version) VALUES ('0002_review_policy')"))
        if not conn.execute(text("SELECT version FROM schema_revisions WHERE version='0003_portfolio_projection'")).first():
            from kuanguard.portfolio import portfolio_metadata
            portfolio_metadata.create_all(conn)
            if conn.dialect.name == "postgresql":
                conn.exec_driver_sql('ALTER TABLE portfolio_connectors ENABLE ROW LEVEL SECURITY')
                conn.exec_driver_sql('ALTER TABLE portfolio_connectors FORCE ROW LEVEL SECURITY')
                conn.exec_driver_sql("""CREATE POLICY tenant_isolation ON portfolio_connectors
                    USING (tenant_id = current_setting('app.tenant_id', true))
                    WITH CHECK (tenant_id = current_setting('app.tenant_id', true))""")
            conn.execute(text("INSERT INTO schema_revisions(version) VALUES ('0003_portfolio_projection')"))
        if not conn.execute(text("SELECT version FROM schema_revisions WHERE version='0004_retest_verification'")).first():
            m.retest_checks.create(conn, checkfirst=True)
            if conn.dialect.name == "postgresql":
                conn.exec_driver_sql('ALTER TABLE retest_checks ENABLE ROW LEVEL SECURITY')
                conn.exec_driver_sql('ALTER TABLE retest_checks FORCE ROW LEVEL SECURITY')
                conn.exec_driver_sql("""CREATE POLICY tenant_isolation ON retest_checks
                    USING (tenant_id = current_setting('app.tenant_id', true))
                    WITH CHECK (tenant_id = current_setting('app.tenant_id', true))""")
            conn.execute(text("INSERT INTO schema_revisions(version) VALUES ('0004_retest_verification')"))
        if not conn.execute(text("SELECT version FROM schema_revisions WHERE version='0005_worker_claim_token'")).first():
            from sqlalchemy import inspect
            if conn.dialect.name == "postgresql":
                conn.exec_driver_sql("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS claim_token VARCHAR(36)")
            elif "claim_token" not in {column["name"] for column in inspect(conn).get_columns("jobs")}:
                conn.exec_driver_sql("ALTER TABLE jobs ADD COLUMN claim_token VARCHAR(36)")
            conn.execute(text("INSERT INTO schema_revisions(version) VALUES ('0005_worker_claim_token')"))
        if not conn.execute(text("SELECT version FROM schema_revisions WHERE version='0006_service_ledger_immutable'")).first():
            if conn.dialect.name == "postgresql":
                conn.exec_driver_sql('CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON entitlement_ledger FOR EACH ROW EXECUTE FUNCTION deny_immutable_change()')
            conn.execute(text("INSERT INTO schema_revisions(version) VALUES ('0006_service_ledger_immutable')"))
        if not conn.execute(text("SELECT version FROM schema_revisions WHERE version='0007_drafts_tickets'")).first():
            for table in (m.form_drafts, m.ticket_messages):
                table.create(conn, checkfirst=True)
                if conn.dialect.name == "postgresql":
                    conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY')
                    conn.exec_driver_sql(f'ALTER TABLE "{table.name}" FORCE ROW LEVEL SECURITY')
                    conn.exec_driver_sql(f'''CREATE POLICY tenant_isolation ON "{table.name}"
                        USING (tenant_id = current_setting('app.tenant_id', true))
                        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))''')
            conn.execute(text("INSERT INTO schema_revisions(version) VALUES ('0007_drafts_tickets')"))
        if not conn.execute(text("SELECT version FROM schema_revisions WHERE version='0008_training_rights'")).first():
            from kuanguard.learning_entitlements import training_metadata, TRAINING_TABLES
            training_metadata.create_all(conn)
            if conn.dialect.name == "postgresql":
                for table in TRAINING_TABLES:
                    conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY')
                    conn.exec_driver_sql(f'ALTER TABLE "{table.name}" FORCE ROW LEVEL SECURITY')
                    conn.exec_driver_sql(f'''CREATE POLICY tenant_isolation ON "{table.name}"
                        USING (tenant_id = current_setting('app.tenant_id', true))
                        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))''')
                    conn.exec_driver_sql(f'CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON "{table.name}" FOR EACH ROW EXECUTE FUNCTION deny_immutable_change()')
            conn.execute(text("INSERT INTO schema_revisions(version) VALUES ('0008_training_rights')"))
        if not conn.execute(text("SELECT version FROM schema_revisions WHERE version='0009_project_execution'")).first():
            for table in EXECUTION_TABLES:
                table.create(conn, checkfirst=True)
                if conn.dialect.name == "postgresql":
                    conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY')
                    conn.exec_driver_sql(f'ALTER TABLE "{table.name}" FORCE ROW LEVEL SECURITY')
                    conn.exec_driver_sql(f'''CREATE POLICY tenant_isolation ON "{table.name}"
                        USING (tenant_id = current_setting('app.tenant_id', true))
                        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))''')
            conn.execute(text("INSERT INTO schema_revisions(version) VALUES ('0009_project_execution')"))
        if not conn.execute(text("SELECT version FROM schema_revisions WHERE version='0010_tenant_lifecycle'")).first():
            m.lifecycle_plans.create(conn, checkfirst=True)
            m.erasure_receipts.create(conn, checkfirst=True)
            if conn.dialect.name == "postgresql":
                conn.exec_driver_sql('ALTER TABLE lifecycle_plans ENABLE ROW LEVEL SECURITY')
                conn.exec_driver_sql('ALTER TABLE lifecycle_plans FORCE ROW LEVEL SECURITY')
                conn.exec_driver_sql('''CREATE POLICY tenant_isolation ON lifecycle_plans
                    USING (tenant_id = current_setting('app.tenant_id', true))
                    WITH CHECK (tenant_id = current_setting('app.tenant_id', true))''')
            conn.execute(text("INSERT INTO schema_revisions(version) VALUES ('0010_tenant_lifecycle')"))
        if conn.dialect.name == "postgresql":
            # psycopg quotes both identifier and password; neither is interpolated into shell or logs.
            from psycopg import sql
            raw = conn.connection.driver_connection
            role = raw.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", ("kuanguard",)).fetchone()
            if not role:
                password = os.environ["POSTGRES_APP_PASSWORD"]
                raw.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD {}")
                            .format(sql.Identifier("kuanguard"), sql.Literal(password)))
            conn.exec_driver_sql("GRANT USAGE ON SCHEMA public TO kuanguard")
            conn.exec_driver_sql("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kuanguard")
            conn.exec_driver_sql("REVOKE UPDATE, DELETE ON wallet_transactions, entitlement_ledger, snapshots, publications, audit_events, schedule_history, attempts FROM kuanguard")
            conn.exec_driver_sql("REVOKE UPDATE, DELETE ON training_entitlements, training_entitlement_ledger FROM kuanguard")
            conn.exec_driver_sql("REVOKE ALL ON schema_revisions FROM kuanguard")
            conn.exec_driver_sql("REVOKE ALL ON erasure_receipts FROM kuanguard")
        print("Versioned schema updates applied/preserved; application role is not database owner")
    # Immutable schema receipt; future schema edits require a new numbered migration.
    out = ROOT / "backend" / "migrations"
    out.mkdir(exist_ok=True)
    schema = "\n\n".join(str(CreateTable(table).compile(dialect=db.dialect)) + ";" for table in m.metadata.sorted_tables)
    schema += "\n" + "\n".join(str(CreateIndex(index).compile(dialect=db.dialect)) + ";" for table in m.metadata.tables.values() for index in table.indexes)
    receipt = out / "0001_initial.sql"
    if not receipt.exists():
        receipt.write_text(schema, encoding="utf-8")
    db.dispose()


if __name__ == "__main__":
    migrate()
