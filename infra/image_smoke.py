"""Run inside an ephemeral KUANGUARD image without network, env file, or mounts."""
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform


def main():
    assert os.getuid() == 10001 and os.getgid() == 10001, "Image must run as its non-root identity"
    assert not Path("/app/.env").exists(), "Host credentials must not be copied into the image"
    assert importlib.util.find_spec("pytest") is None, "Development dependencies must not enter the runtime image"
    modules = ("fastapi", "psycopg", "sqlalchemy", "cryptography", "reportlab", "pypdf", "docx", "pptx", "openpyxl")
    for module in modules:
        importlib.import_module(module)
    importlib.import_module("kuanguard.api")
    importlib.import_module("kuanguard.worker")
    probe = Path("/data/storage/image-smoke.txt")
    payload = b"KUANGUARD synthetic non-root image storage probe\n"
    probe.write_bytes(payload)
    assert probe.read_bytes() == payload
    checksum = hashlib.sha256(probe.read_bytes()).hexdigest()
    probe.unlink()
    limits = {name: Path("/sys/fs/cgroup", name).read_text().strip() for name in ("cpu.max", "memory.max", "pids.max")}
    quota, period = map(int, limits["cpu.max"].split())
    assert quota / period <= 1
    assert int(limits["memory.max"]) == 1024 * 1024 * 1024
    assert int(limits["pids.max"]) == 128
    fonts = list(Path("/usr/share/fonts/opentype/noto").glob("*CJK*"))
    assert fonts, "Redistributable CJK fallback fonts must be present"
    source_paths = sorted([*[path for root in ("backend", "scripts") for path in Path(root).rglob("*") if path.is_file()], Path("pyproject.toml"), Path("uv.lock")])
    result = {"state": "passed", "python": platform.python_version(), "uid": os.getuid(), "gid": os.getgid(),
              "api_worker_import": "passed", "non_root_storage_write_read_sha256": checksum,
              "cgroup_limits": limits, "fallback_cjk_font_files": len(fonts),
              "approved_report_font_embedding_qa": "unverified", "host_env_copied": False,
              "network": "none", "source_database_or_objects_mounted": False,
              "source_files_sha256": {path.as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths},
              "dependencies": {package: importlib.metadata.version(package) for package in
                               ("fastapi", "psycopg", "sqlalchemy", "cryptography", "reportlab", "pypdf")}}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
