#!/usr/bin/env python3
"""Checksummed database + private-object backup and isolated restore rehearsal.

SQLite uses the online backup API. PostgreSQL uses pg_dump custom format and
pg_restore, either installed clients or the existing Compose db service. Database
secrets stay in environment variables/the container. No shell interpolation is used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import subprocess
import sys


class BackupError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def manifest_hash(manifest: dict):
    return hashlib.sha256(json.dumps({key: value for key, value in manifest.items() if key != "manifest_sha256"},
                                     sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def is_link(path: Path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def contained_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative)
    if (not relative or parts.is_absolute() or "\\" in relative or ":" in relative
            or any(part in {".", ".."} or part.endswith((".", " ")) for part in relative.split("/"))):
        raise BackupError("Invalid relative backup path")
    target = root.joinpath(*parts.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise BackupError("Backup path escapes its root")
    current = target
    while current != root:
        if is_link(current):
            raise BackupError("Symlinks and junctions are not accepted in backup data")
        current = current.parent
    return target


def files_under(root: Path) -> list[Path]:
    if not root.is_dir() or is_link(root):
        raise BackupError("Object root must be a real existing directory")
    result = []
    for folder, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(folder) / name
            if is_link(path):
                raise BackupError("Object tree contains a symlink or junction")
        result.extend(Path(folder) / name for name in files)
    return sorted(result)


def sqlite_integrity(path: Path):
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise BackupError("SQLite integrity check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise BackupError("SQLite foreign key check failed")
    finally:
        connection.close()


class PostgreSQL:
    def __init__(self, database: str, user: str, compose_file: Path | None = None, service="db"):
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,62}", database) or not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,62}", user):
            raise BackupError("PostgreSQL database and user names must be simple identifiers")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", service):
            raise BackupError("Invalid Compose service")
        self.database, self.user = database, user
        self.prefix = ["docker", "compose", "-f", str(compose_file.resolve()), "exec", "-T", service] if compose_file else []

    def command(self, program: str, *args: str, input_file=None, output_file=None, data: bytes | None = None):
        command = self.prefix + [program, "--username", self.user, *args]
        with open(input_file, "rb") if input_file else open(os.devnull, "rb") as source:
            if output_file:
                with Path(output_file).open("xb") as destination:
                    result = subprocess.run(command, stdin=source, stdout=destination, stderr=subprocess.PIPE, timeout=600, check=False)
            elif data is not None:
                result = subprocess.run(command, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600, check=False)
            else:
                result = subprocess.run(command, stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600, check=False)
        if result.returncode:
            # Do not print database connection details or provider errors containing secrets.
            raise BackupError(f"{program} failed with exit {result.returncode}; inspect the database privately")
        return result.stdout

    def dump(self, path: Path):
        self.command("pg_dump", "--dbname", self.database, "--format=custom", "--no-owner", "--no-acl", output_file=path)
        with path.open("rb") as stream:
            if stream.read(5) != b"PGDMP":
                raise BackupError("pg_dump did not produce a PostgreSQL custom archive")

    def empty_restore_database(self, target: str):
        if not re.fullmatch(r"kuanguard_restore_[a-z0-9_]{1,40}", target) or target == self.database:
            raise BackupError("Restore only creates an isolated kuanguard_restore_* database; source and existing databases are never overwritten")
        # Target has a strict identifier grammar. Query uses SQL literals only after this check.
        exists = self.command("psql", "--dbname", "postgres", "--tuples-only", "--no-align", "--command",
                              f"SELECT 1 FROM pg_database WHERE datname = '{target}'").decode().strip()
        if exists:
            raise BackupError("Restore database already exists; choose a new isolated target")
        self.command("createdb", "--template=template0", target)

    def restore(self, path: Path, target: str):
        self.empty_restore_database(target)
        self.command("pg_restore", "--dbname", target, "--no-owner", "--no-acl", "--exit-on-error", "--single-transaction", input_file=path)
        # Check persisted tables are queryable after the transaction and record database-native counts.
        schema = self.command("psql", "--dbname", target, "--tuples-only", "--no-align", "--command",
                              "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'").decode().strip()
        return {"database": target, "public_table_count": int(schema), "restore_transaction": "committed"}


def validate_metadata(metadata: dict):
    allowed = {"schema_version", "deployment_commit", "config_version", "brand", "apex", "business_timezone", "object_backend", "key_references"}
    if set(metadata) - allowed:
        raise BackupError("Metadata only accepts public config versions and secret-manager key references")
    if not isinstance(metadata.get("key_references", []), list) or any(not isinstance(ref, str) or not ref.startswith("secret://") for ref in metadata.get("key_references", [])):
        raise BackupError("Only secret:// references are accepted; encryption keys and credentials must be stored separately")


def create_backup(destination: Path, objects: Path, *, sqlite_path: Path | None = None,
                  postgres: PostgreSQL | None = None, metadata=None, writers_paused=False) -> dict:
    if not writers_paused:
        raise BackupError("Pause API/worker writes before backing up DB and mutable objects; --writers-paused is an operator attestation")
    if bool(sqlite_path) == bool(postgres):
        raise BackupError("Select exactly one SQLite or PostgreSQL database")
    metadata = metadata or {}
    validate_metadata(metadata)
    objects = objects.resolve()
    if destination.exists() or destination.resolve().is_relative_to(objects):
        raise BackupError("Backup destination must be new and outside the source object tree")
    if sqlite_path and (not sqlite_path.is_file() or is_link(sqlite_path)):
        raise BackupError("SQLite source must be an existing regular database file")
    source_files = files_under(objects)
    source_manifest = {file.relative_to(objects).as_posix(): {"size": file.stat().st_size, "sha256": sha256(file)} for file in source_files}
    destination.mkdir(parents=True)
    manifest = {"schema_version": 1, "created_at": now(), "state": "incomplete", "database": {"type": "sqlite" if sqlite_path else "postgresql"},
                "consistency": "operator_attested_writers_paused_and_object_hash_readback", "files": [], "metadata": metadata,
                "encryption": "not_performed_by_this_tool_use_an_encrypted_destination", "metadata_contains_secret_values": False,
                "data_classification": "private_database_and_objects_may_contain_sensitive_material"}
    try:
        db_name = "database.sqlite3" if sqlite_path else "database.dump"
        db_target = destination / db_name
        if sqlite_path:
            connection = sqlite3.connect(sqlite_path.resolve().as_uri() + "?mode=ro", uri=True)
            backup_connection = sqlite3.connect(db_target)
            try:
                connection.backup(backup_connection)
            finally:
                backup_connection.close()
                connection.close()
            sqlite_integrity(db_target)
        else:
            postgres.dump(db_target)
        manifest["database"]["file"] = db_name
        manifest["files"].append({"path": db_name, "size": db_target.stat().st_size, "sha256": sha256(db_target), "kind": "database"})
        for relative, expected in source_manifest.items():
            original = objects / relative
            target = contained_path(destination, "objects/" + relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
            if target.stat().st_size != expected["size"] or sha256(target) != expected["sha256"] or sha256(original) != expected["sha256"]:
                raise BackupError("Object changed during backup; stop writers and repeat into a new destination")
            manifest["files"].append({"path": "objects/" + relative, **expected, "kind": "object"})
        final_paths = {file.relative_to(objects).as_posix() for file in files_under(objects)}
        if final_paths != set(source_manifest):
            raise BackupError("Object set changed during backup")
        if any(sha256(objects / relative) != row["sha256"] for relative, row in source_manifest.items()):
            raise BackupError("Object content changed during final backup readback")
        manifest.update({"state": "complete", "completed_at": now(), "object_count": len(source_manifest), "total_bytes": sum(row["size"] for row in manifest["files"])})
        manifest["manifest_sha256"] = manifest_hash(manifest)
    finally:
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_backup(directory: Path, expected_hash: str | None = None) -> dict:
    if is_link(directory):
        raise BackupError("Backup root must not be a symlink or junction")
    directory = directory.resolve()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("state") != "complete" or manifest.get("manifest_sha256") != manifest_hash(manifest):
        raise BackupError("Backup manifest is incomplete or its checksum failed")
    if expected_hash is not None and expected_hash != manifest["manifest_sha256"]:
        raise BackupError("Backup does not match the separately recorded manifest checksum")
    names = set()
    databases = []
    for entry in manifest["files"]:
        folded = entry["path"].casefold()
        if folded in names:
            raise BackupError("Duplicate or case-colliding backup path")
        names.add(folded)
        path = contained_path(directory, entry["path"])
        if not path.is_file() or path.stat().st_size != entry["size"] or sha256(path) != entry["sha256"]:
            raise BackupError("Backup file is missing or its checksum failed")
        if entry["kind"] == "database":
            databases.append(entry["path"])
        elif entry["kind"] != "object" or not entry["path"].startswith("objects/"):
            raise BackupError("Unrecognized backup member")
    database = manifest["database"]
    expected_name = {"sqlite": "database.sqlite3", "postgresql": "database.dump"}.get(database["type"])
    if databases != [expected_name] or database["file"] != expected_name:
        raise BackupError("Backup database declaration mismatch")
    actual = {path.relative_to(directory).as_posix().casefold() for path in files_under(directory)}
    if actual != names | {"manifest.json"}:
        raise BackupError("Unexpected extra files in backup; verify the immutable archive")
    if database["type"] == "sqlite":
        sqlite_integrity(directory / database["file"])
    else:
        with (directory / database["file"]).open("rb") as stream:
            if stream.read(5) != b"PGDMP":
                raise BackupError("PostgreSQL archive header mismatch")
    return manifest


def restore_backup(directory: Path, target: Path, expected_hash: str, *, allowed_root: Path,
                   postgres: PostgreSQL | None = None, target_database: str | None = None) -> dict:
    manifest = verify_backup(directory, expected_hash)
    allowed_root = allowed_root.resolve()
    resolved_target = target.resolve()
    if resolved_target == allowed_root or not resolved_target.is_relative_to(allowed_root) or target.exists():
        raise BackupError("Restore target must be a new directory strictly beneath the specified allowed restore root")
    # Check existing ancestors before creating anything. No recursive deletion or overwrite occurs.
    current = target.absolute().parent
    while current != current.parent:
        if is_link(current):
            raise BackupError("Restore target ancestor is a symlink or junction")
        current = current.parent
    pg_mode = manifest["database"]["type"] == "postgresql"
    if pg_mode and (not postgres or not target_database):
        raise BackupError("PostgreSQL restore requires the client/Compose connection and a new isolated target database")
    if not pg_mode and (postgres or target_database):
        raise BackupError("SQLite backup cannot be restored using PostgreSQL arguments")
    target.mkdir(parents=True)
    receipt = {"schema_version": 1, "started_at": now(), "backup_manifest_sha256": expected_hash, "state": "incomplete", "object_count": 0}
    try:
        for entry in manifest["files"]:
            if entry["kind"] == "database" and pg_mode:
                continue
            source = contained_path(directory.resolve(), entry["path"])
            destination = contained_path(target, entry["path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            if sha256(destination) != entry["sha256"]:
                raise BackupError("Restored file checksum mismatch")
            if entry["kind"] == "object":
                receipt["object_count"] += 1
        if pg_mode:
            receipt["database"] = postgres.restore(directory / manifest["database"]["file"], target_database)
        else:
            sqlite_integrity(target / manifest["database"]["file"])
            receipt["database"] = {"type": "sqlite", "integrity_check": "ok"}
        receipt.update({"state": "restored", "completed_at": now(), "file_checksums": "passed",
                        "application_job_recovery": "unverified_requires_application_reconciliation",
                        "rpo": "not_measured", "rto": "single_local_rehearsal_only"})
    finally:
        (target / "restore-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("backup")
    create.add_argument("--out", required=True)
    create.add_argument("--objects", required=True)
    create.add_argument("--sqlite")
    create.add_argument("--postgres", action="store_true")
    create.add_argument("--writers-paused", action="store_true")
    create.add_argument("--metadata")
    verify = sub.add_parser("verify")
    verify.add_argument("--backup", required=True)
    verify.add_argument("--manifest-sha256")
    restore = sub.add_parser("restore")
    restore.add_argument("--backup", required=True)
    restore.add_argument("--out", required=True)
    restore.add_argument("--allowed-root", required=True)
    restore.add_argument("--manifest-sha256", required=True)
    restore.add_argument("--target-database")
    for command in (create, restore):
        command.add_argument("--compose-file")
        command.add_argument("--service", default="db")
        command.add_argument("--database", default="kuanguard")
        command.add_argument("--user", default="kuanguard")
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            result = verify_backup(Path(args.backup), args.manifest_sha256)
        else:
            pg = PostgreSQL(args.database, args.user, Path(args.compose_file) if args.compose_file else None, args.service) if (args.command == "backup" and args.postgres) or (args.command == "restore" and args.target_database) else None
            if args.command == "backup":
                metadata = json.loads(Path(args.metadata).read_text(encoding="utf-8")) if args.metadata else {}
                result = create_backup(Path(args.out), Path(args.objects), sqlite_path=Path(args.sqlite) if args.sqlite else None,
                                       postgres=pg, metadata=metadata, writers_paused=args.writers_paused)
            else:
                result = restore_backup(Path(args.backup), Path(args.out), args.manifest_sha256,
                                        allowed_root=Path(args.allowed_root), postgres=pg, target_database=args.target_database)
        print(json.dumps({key: result[key] for key in ("state", "manifest_sha256", "object_count", "file_checksums", "database") if key in result}))
        return 0
    except (BackupError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"state": "refused", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
