"""Regenerate six synthetic demonstration bundles in a new, empty destination.

Use the bundled Python runtime for artifact authoring. This is local data only.
"""

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from kuanguard.parsers import parse_assessment
from kuanguard.reports import build_snapshot, generate_bundle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "samples/reports/bundles_final")
    args = parser.parse_args()
    inputs = Path(__file__).parent / "inputs"
    snapshots = {}
    for name, filename, service, assets in [
        ("va_initial", "va_initial.nessus", "VA", ["192.0.2.10", "192.0.2.20", "192.0.2.30"]),
        ("wva_initial", "wva_initial.xml", "WVA", ["https://app.example.test", "https://portal.example.test"]),
        ("shc_initial", "shc_initial.json", "SHC", ["192.0.2.10", "192.0.2.20"]),
        ("pt_initial", "pt_initial.json", "PT", ["https://app.example.test", "https://portal.example.test"]),
        ("source_initial", "source_initial.sarif", "SOURCE", ["src/demo.py", "src/excluded.py"]),
        ("va_retest", "va_retest.nessus", "VA", ["192.0.2.10", "192.0.2.20", "192.0.2.30"]),
    ]:
        parsed = parse_assessment(filename, (inputs / filename).read_bytes(), service, assets)
        if parsed["errors"]:
            raise ValueError(f"{name}: {parsed['errors']}")
        context = {"batch_id": f"synthetic-{name}", "service_code": service, "scope_version": "synthetic-scope/1",
                   "reviewer_id": "synthetic-reviewer", "reviewed_at": "2026-09-10T06:00:00Z", "report_version": "1",
                   "synthetic": True, "project_name": "2026 年度合成示範專案", "trace_id": f"trace-synthetic-{name}"}
        if name == "va_retest":
            baseline = snapshots["va_initial"]
            context["baseline_snapshot"] = baseline
            context["verified_absent"] = [{"occurrence_id": f["occurrence_id"], "reviewer_id": "synthetic-reviewer",
                                           "method": "nessus", "scope_confirmed": True,
                                           "evidence": "合成驗證紀錄 RETEST-001；確認原連接埠與原檢測方法完成。"}
                                          for f in baseline["findings"] if f["source_id"] == "100001"]
        snapshot = build_snapshot(parsed, context)
        snapshots[name] = snapshot
        destination = args.output / name
        manifest = generate_bundle(snapshot, destination)
        (destination / "snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"sample": name, "snapshot_id": snapshot["snapshot_id"], "files": len(manifest["artifacts"]),
                          "risk_instances": snapshot["statistics"]["occurrence_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
