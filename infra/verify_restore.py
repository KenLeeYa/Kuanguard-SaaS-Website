"""Compare a paused local PostgreSQL source with its isolated restored database.

Only counts and SHA-256 digests leave this process; private table rows are not logged.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from backup_restore import BackupError, PostgreSQL  # noqa: E402


def snapshot(database: PostgreSQL):
    table_names = database.command(
        "psql", "--no-psqlrc", "--dbname", database.database, "--quiet", "--tuples-only", "--no-align",
        "--command", "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name",
    ).decode("utf-8").splitlines()
    if not table_names:
        raise BackupError("Expected populated KUANGUARD public schema; no table inventory was returned")
    queries = []
    for table in table_names:
        if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", table):
            raise BackupError("Unexpected table identifier; manual read-only verification required")
        # One statement shares one snapshot; C ordering is independent of restore heap order.
        queries.append(f"SELECT json_build_object('table', '{table}', 'rows', count(*), 'ordered_json', "
                       f"COALESCE(json_agg(row_to_json(t) ORDER BY row_to_json(t)::text COLLATE \"C\"), '[]'::json)::text) "
                       f'FROM public."{table}" AS t')
    data = database.command(
        "psql", "--no-psqlrc", "--dbname", database.database, "--quiet", "--tuples-only", "--no-align",
        "--set", "ON_ERROR_STOP=1", "--file", "-", data=(" UNION ALL ".join(queries) + ";\n").encode("utf-8"),
    )
    result = {}
    for line in data.decode("utf-8").splitlines():
        table = json.loads(line)
        # Hash native JSON text directly; Python float conversion must not round financial NUMERIC values.
        rows = table["ordered_json"].encode("utf-8")
        result[table["table"]] = {"rows": table["rows"], "ordered_json_sha256": hashlib.sha256(rows).hexdigest()}
    if set(result) != set(table_names):
        raise BackupError("Table snapshot was incomplete")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-file", required=True)
    parser.add_argument("--source", default="kuanguard")
    parser.add_argument("--restored", required=True)
    parser.add_argument("--user", default="kuanguard_owner")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"kuanguard_restore_[a-z0-9_]{1,40}", args.restored) or args.source == args.restored:
        raise BackupError("Comparison target must be an isolated restore database")
    output = Path(args.out)
    if output.exists():
        raise BackupError("Preserve previous comparison evidence; choose a new output")
    source = snapshot(PostgreSQL(args.source, args.user, Path(args.compose_file)))
    restored = snapshot(PostgreSQL(args.restored, args.user, Path(args.compose_file)))
    differences = [name for name in sorted(source.keys() | restored.keys()) if source.get(name) != restored.get(name)]
    evidence = {"observed_at": datetime.now(timezone.utc).isoformat(), "source_database": args.source,
                "restored_database": args.restored, "equal": not differences, "different_tables": differences,
                "table_count": len(source), "total_rows": sum(table["rows"] for table in source.values()),
                "source_tables": source, "restored_tables": restored, "private_rows_logged": False,
                "scope": "read_only_public_table_data_comparison_during_operator_paused_writes"}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, indent=2)
        stream.write("\n")
    print(json.dumps({key: evidence[key] for key in ("equal", "table_count", "total_rows", "different_tables")}))
    return 0 if not differences else 1


if __name__ == "__main__":
    raise SystemExit(main())
