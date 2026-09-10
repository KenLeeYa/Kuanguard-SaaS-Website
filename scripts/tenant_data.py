"""Private operator exports and reviewed erasure plans; no implicit execute mode."""
import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / ".env")
from kuanguard import models as m  # noqa: E402
from kuanguard.config import settings  # noqa: E402
from kuanguard.db import add, all_rows, one, set_tenant  # noqa: E402
from kuanguard.lifecycle import canonical, erasure_manifest, execute_erasure, export_archive  # noqa: E402
from kuanguard.security import digest  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("export", "plan-erasure", "execute-erasure"))
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--request", required=True, dest="request_id")
    parser.add_argument("--path", type=Path, required=True, help="Private archive or exact plan JSON path")
    parser.add_argument("--confirm-digest", default="")
    args = parser.parse_args()
    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        raise ValueError("Dedicated privileged migration connection is required")
    runtime, administrative = make_url(settings().database_url), make_url(url)
    if (runtime.host, runtime.port, runtime.database) != (administrative.host, administrative.port, administrative.database):
        raise ValueError("Migration target must exactly match the configured KUANGUARD runtime database")
    db = create_engine(url)
    try:
        if args.operation == "execute-erasure":
            manifest = json.loads(args.path.read_text(encoding="utf-8"))
            if manifest["tenant_id"] != args.tenant or manifest["request_id"] != args.request_id:
                raise ValueError("CLI tenant/request do not match the reviewed plan")
            result = execute_erasure(db, manifest, args.confirm_digest)
        else:
            with db.begin() as conn:
                set_tenant(conn, args.tenant, mutation=True)
                request = one(conn, m.deletion_requests, args.tenant, m.deletion_requests.c.id == args.request_id)
                if not request:
                    raise ValueError("Authenticated customer request is required")
                if args.operation == "export":
                    if request["data_class"] != "data_export" or request["status"] not in {"requested", "exported"}:
                        raise ValueError("This request is not an authorized export request")
                    if all_rows(conn, m.jobs, None, m.jobs.c.tenant_id == args.tenant, m.jobs.c.status == "running"):
                        raise ValueError("Wait for running tenant jobs before a consistent export")
                    manifest = export_archive(conn, args.tenant, args.path)
                    conn.execute(m.deletion_requests.update().where(m.deletion_requests.c.id == request["id"],
                        m.deletion_requests.c.tenant_id == args.tenant).values(status="exported"))
                    add(conn, m.audit_events, args.tenant, actor_id="operator-cli", action="lifecycle.export",
                        resource_id=request["id"], summary=f"private archive manifest={manifest['manifest_sha256']}")
                    result = {"status": "exported", "manifest_sha256": manifest["manifest_sha256"],
                              "tables": len(manifest["tables"]), "objects": len(manifest["objects"])}
                else:
                    manifest = erasure_manifest(conn, args.tenant, args.request_id)
                    args.path.parent.mkdir(parents=True, exist_ok=True)
                    with args.path.open("xb") as output:
                        output.write(canonical(manifest))
                    result = {"status": "planned_only", "manifest_sha256": digest(canonical(manifest)),
                              "tables": len(manifest["tables"]), "objects": len(manifest["objects"])}
        print(json.dumps(result))
    finally:
        db.dispose()


if __name__ == "__main__":
    main()
