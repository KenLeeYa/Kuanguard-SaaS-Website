import copy
import csv
import hashlib
import io
import json
import zipfile

import pytest
from openpyxl import load_workbook

from kuanguard.parsers import MAX_BYTES, normalize_asset, parse_assessment
from kuanguard.reports import build_snapshot, generate_bundle


def csv_input(rows):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["Plugin ID", "Host", "Risk", "Name", "Port", "Protocol", "Description", "Solution"])
    writer.writerows(rows)
    return buffer.getvalue().encode()


def nessus(items="", host="192.0.2.10", completed=True):
    properties = '<HostProperties><tag name="HOST_START">2026-09-10T01:00:00Z</tag><tag name="HOST_END">2026-09-10T02:00:00Z</tag></HostProperties>' if completed else ""
    return f'<NessusClientData_v2><Report name="Synthetic"><ReportHost name="{host}">{properties}{items}</ReportHost></Report></NessusClientData_v2>'.encode()


def item(plugin="1001", port=443, severity=3):
    return f'<ReportItem pluginID="{plugin}" pluginName="Synthetic finding" port="{port}" protocol="tcp" severity="{severity}"><description>合成弱點說明</description><solution>依維護程序修補</solution></ReportItem>'


def context(service="VA", **extra):
    return {"batch_id": "batch-synthetic-01", "service_code": service, "scope_version": "1", "reviewer_id": "synthetic-reviewer",
            "reviewed_at": "2026-09-10T02:00:00Z", "report_version": "1", "synthetic": True, **extra}


def test_nessus_keeps_ports_in_identity_and_zero_finding_host_coverage():
    data = nessus(item() + item(port=8443) + item())
    parsed = parse_assessment("scan.nessus", data, "VA", ["192.0.2.10", "192.0.2.20"])
    assert not parsed["errors"]
    assert len(parsed["findings"]) == 2
    assert parsed["metadata"]["duplicate_rows"] == 1
    assert parsed["coverage"] == [{"asset": "192.0.2.10", "status": "completed"}, {"asset": "192.0.2.20", "status": "not_tested"}]
    clean = parse_assessment("zero.nessus", nessus(), "VA", ["192.0.2.10"])
    assert clean["findings"] == [] and clean["coverage"][0]["status"] == "completed"
    unproven = parse_assessment("zero.nessus", nessus(completed=False), "VA", ["192.0.2.10"])
    assert unproven["coverage"][0]["status"] == "insufficient"


def test_csv_information_unknown_and_missing_scope_do_not_become_low_or_complete():
    parsed = parse_assessment("scan.csv", csv_input([["1", "192.0.2.10", "None", "Inventory", "", "", "", ""],
                                                   ["2", "192.0.2.10", "", "Missing severity", "443", "tcp", "", ""],
                                                   ["3", "192.0.2.10", "High", "Patch", "443", "tcp", "", ""]]), "VA", ["192.0.2.10", "192.0.2.20"])
    assert not parsed["errors"]
    assert [f["severity"] for f in parsed["findings"]] == ["Informational", "Unknown", "High"]
    snapshot = build_snapshot(parsed, context())
    assert snapshot["statistics"]["severity_counts"] == {"Critical": 0, "High": 1, "Medium": 0, "Low": 0}
    assert snapshot["statistics"]["completed_asset_count"] == 0
    assert snapshot["statistics"]["informational_count"] == 1
    assert snapshot["statistics"]["unknown_count"] == 1


def test_definition_occurrence_and_affected_asset_counts_are_distinct():
    rows = [["1001", host, "High", "Synthetic", port, "tcp", "", ""] for host, port in [("192.0.2.1", 443), ("192.0.2.1", 8443), ("192.0.2.2", 443)]]
    parsed = parse_assessment("scan.csv", csv_input(rows), "VA", ["192.0.2.1", "192.0.2.2"])
    stats = build_snapshot(parsed, context())["statistics"]
    assert (stats["definition_count"], stats["occurrence_count"], stats["affected_asset_count"]) == (1, 3, 2)


def test_duplicate_conflicting_severity_requires_resolution():
    parsed = parse_assessment("scan.csv", csv_input([["1", "192.0.2.1", s, "Synthetic", 443, "tcp", "", ""] for s in ("High", "Low")]), "VA", [])
    assert parsed["errors"][0].startswith("CONFLICTING_DUPLICATE")
    assert parsed["findings"] == []


@pytest.mark.parametrize("filename,content,service", [
    ("bad.nessus", b'<!DOCTYPE a [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><NessusClientData_v2>&xxe;</NessusClientData_v2>', "VA"),
    ("bad.nessus", b'<NessusClientData_v2><script>evil()</script></NessusClientData_v2>', "VA"),
    ("bad.zip", b"PK\x03\x04evil", "SOURCE"),
    ("bad.sarif", b"PK\x03\x04evil", "SOURCE"),
    ("bad.html", b"<script>alert(1)</script>", "VA"),
    ("bad.json", b'{"schema":"kuanguard.shc/1","schema":"spoof"}', "SHC"),
    ("bad.csv", b"Plugin ID,Host,Risk,Name\n1,192.0.2.1,High", "VA"),
    ("bad.csv", b"\xff\xfeinvalid", "VA"),
])
def test_malicious_or_malformed_input_is_rejected_without_partial_results(filename, content, service):
    parsed = parse_assessment(filename, content, service, [])
    assert parsed["errors"]
    assert parsed["findings"] == [] and parsed["coverage"] == []


def test_large_input_is_rejected():
    assert parse_assessment("big.csv", b"a" * (MAX_BYTES + 1), "VA", [])["errors"][0].startswith("FILE_TOO_LARGE")


def test_ipv6_normalization_never_guesses_port():
    assert normalize_asset("2001:0db8::1") == "2001:db8::1"
    assert normalize_asset("[2001:db8::1]:443") == "2001:db8::1"
    parsed = parse_assessment("ipv6.csv", csv_input([["1", "2001:db8::443", "Low", "Synthetic", "", "tcp", "", ""]]), "VA", [])
    assert parsed["findings"][0]["asset"] == "2001:db8::443"
    assert parsed["findings"][0]["port"] is None
    parsed = parse_assessment("ipv6.csv", csv_input([["1", "[2001:db8::1]:443", "Low", "Synthetic", "", "tcp", "", ""]]), "VA", [])
    assert parsed["findings"][0]["port"] == 443


def test_appscan_unknown_native_schema_is_rejected_and_mapped_profile_masks_identity():
    native = parse_assessment("appscan.xml", b'<XmlReport productVersion="10.7"><Issues /></XmlReport>', "WVA", [])
    assert native["errors"][0].startswith("UNSUPPORTED_APPSCAN_SCHEMA")
    xml = '<XmlReport schemaVersion="kuanguard-appscan-1" productVersion="synthetic"><Issues>{}</Issues><Coverage><Target url="https://app.example.test" status="completed" /></Coverage></XmlReport>'
    issues = ''.join(f'<Issue IssueTypeID="A1" Severity="Critical"><Name>合成測試</Name><Url>https://app.example.test/login?token={token}&amp;view=home</Url><Method>POST</Method><Parameter>token</Parameter></Issue>' for token in ("secret-one", "secret-two"))
    parsed = parse_assessment("appscan.xml", xml.format(issues).encode(), "WVA", ["https://app.example.test"])
    assert not parsed["errors"] and len(parsed["findings"]) == 2
    assert all("secret-" not in finding["location"] for finding in parsed["findings"])
    assert parsed["findings"][0]["fingerprint"] != parsed["findings"][1]["fingerprint"]
    assert parsed["findings"][0]["severity"] == "Critical"


def test_shc_evidence_insufficiency_and_denominator():
    data = {"schema": "kuanguard.shc/1", "checklist_version": "synthetic/1", "coverage": [{"asset": "192.0.2.10", "status": "completed"}], "checks": [
        {"id": "C1", "asset": "192.0.2.10", "title": "備份紀錄", "severity": "High", "status": "passed", "expected": "daily", "observed": "daily", "evidence": "", "reviewer": "reviewer"},
        {"id": "C2", "asset": "192.0.2.10", "title": "不適用案例", "severity": "Low", "status": "not_applicable", "applicability_reason": "此合成資產沒有該元件"},
        {"id": "C3", "asset": "192.0.2.10", "title": "日誌紀錄", "severity": "Medium", "status": "passed", "expected": "enabled", "observed": "enabled", "evidence": "synthetic evidence", "reviewer": "reviewer"}]}
    parsed = parse_assessment("shc.json", json.dumps(data).encode(), "SHC", ["192.0.2.10"])
    assert not parsed["errors"]
    assert parsed["findings"][0]["check_status"] == "insufficient"
    assert parsed["coverage"][0]["status"] == "insufficient"
    stats = build_snapshot(parsed, context("SHC"))["statistics"]
    assert stats["shc"]["pass_rate"] == 0.5
    assert stats["shc"]["applicable_count"] == 2
    assert stats["occurrence_count"] == 0


def test_shc_individual_pass_does_not_prove_full_checklist_coverage():
    data = {"schema": "kuanguard.shc/1", "checklist_version": "1", "checks": [{"id": "C1", "asset": "a", "title": "one check", "severity": "Low", "status": "passed", "expected": "on", "observed": "on", "evidence": "proof", "reviewer": "reviewer"}]}
    assert parse_assessment("shc.json", json.dumps(data).encode(), "SHC", ["a"])["coverage"][0]["status"] == "insufficient"


def test_pt_unreviewed_cannot_become_report_snapshot():
    data = {"schema": "kuanguard.pt/1", "authorization_reference": "synthetic-auth", "methodology": "manual-synthetic", "test_window": "2026-09-10T01:00Z/02:00Z", "stop_conditions": "owner request", "findings": [
        {"id": "PT1", "asset": "https://app.example.test", "title": "synthetic access issue", "severity": "High", "reviewed": False}]}
    parsed = parse_assessment("pt.json", json.dumps(data).encode(), "PT", [])
    assert not parsed["errors"]
    with pytest.raises(ValueError, match="人工覆核"):
        build_snapshot(parsed, context("PT"))
    data["findings"][0].update(reviewed=True, reviewer="synthetic-reviewer")
    assert build_snapshot(parse_assessment("pt.json", json.dumps(data).encode(), "PT", []), context("PT"))["service_code"] == "PT"


def sarif(results, *, completed=True, disabled=False, paths=None):
    return json.dumps({"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "synthetic-tool", "version": "1", "rules": [{"id": "R1", "shortDescription": {"text": "Synthetic source finding"}, "defaultConfiguration": {"enabled": not disabled}}]}},
        "invocations": [{"executionSuccessful": completed}], "properties": {"kuanguard": {"covered_paths": paths if paths is not None else ["src/demo.py"]}}, "results": results}]}).encode()


def source_result(line=1):
    return {"ruleId": "R1", "level": "error", "message": {"text": "合成規則發現"}, "partialFingerprints": {"stable": "source-1"}, "locations": [{"physicalLocation": {"artifactLocation": {"uri": "src/demo.py"}, "region": {"startLine": line}}}]}


def test_sarif_line_shift_preserves_identity_and_scan_failure_does_not_clear_findings():
    baseline = build_snapshot(parse_assessment("source.sarif", sarif([source_result()]), "SOURCE", ["src/demo.py"]), context("SOURCE"))
    shifted = build_snapshot(parse_assessment("source.sarif", sarif([source_result(90)]), "SOURCE", ["src/demo.py"]), context("SOURCE", baseline_snapshot=baseline))
    assert shifted["retest"][0]["status"] == "persistent"
    failed = build_snapshot(parse_assessment("source.sarif", sarif([], completed=False), "SOURCE", ["src/demo.py"]), context("SOURCE", baseline_snapshot=baseline))
    assert failed["retest"][0]["status"] == "not_covered"
    disabled = build_snapshot(parse_assessment("source.sarif", sarif([], disabled=True), "SOURCE", ["src/demo.py"]), context("SOURCE", baseline_snapshot=baseline))
    assert disabled["retest"][0]["status"] == "not_covered"


def test_sarif_missing_coverage_not_complete_and_traversal_rejected():
    parsed = parse_assessment("source.sarif", sarif([], paths=[]), "SOURCE", ["src/demo.py"])
    assert parsed["coverage"][0]["status"] == "not_tested"
    result = source_result()
    result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] = "../../outside.py"
    assert parse_assessment("source.sarif", sarif([result]), "SOURCE", [])["errors"]


def test_sarif_distinct_locations_without_stable_fingerprint_are_not_collapsed():
    first, second = source_result(10), source_result(90)
    first.pop("partialFingerprints")
    second.pop("partialFingerprints")
    parsed = parse_assessment("source.sarif", sarif([first, second]), "SOURCE", ["src/demo.py"])
    assert len(parsed["findings"]) == 2
    snapshot = build_snapshot(parsed, context("SOURCE"))
    assert len({f["occurrence_id"] for f in snapshot["findings"]}) == 2


def test_retest_absence_requires_proof_method_scope_and_completed_coverage():
    baseline = build_snapshot(parse_assessment("scan.nessus", nessus(item()), "VA", ["192.0.2.10"]), context())
    current = parse_assessment("zero.nessus", nessus(), "VA", ["192.0.2.10"])
    assert build_snapshot(current, context(baseline_snapshot=baseline))["retest"][0]["status"] == "indeterminate"
    proof = {"occurrence_id": baseline["findings"][0]["occurrence_id"], "evidence": "個別驗證輸出已覆核", "reviewer_id": "reviewer", "method": "nessus", "scope_confirmed": True}
    assert build_snapshot(current, context(baseline_snapshot=baseline, verified_absent=[proof]))["retest"][0]["status"] == "verified_remediated"
    proof["method"] = "different-tool"
    assert build_snapshot(current, context(baseline_snapshot=baseline, verified_absent=[proof]))["retest"][0]["status"] == "indeterminate"


def test_csv_precedence_records_difference_and_uses_proven_nessus_coverage():
    parsed_csv = parse_assessment("scan.csv", csv_input([["1001", "192.0.2.10", "Low", "CSV baseline", 443, "tcp", "", ""]]), "VA", ["192.0.2.10"])
    parsed_xml = parse_assessment("scan.nessus", nessus(item() + item(plugin="1002")), "VA", ["192.0.2.10"])
    snapshot = build_snapshot(parsed_xml, context(additional_sources=[parsed_csv]))
    assert len(snapshot["findings"]) == 1 and snapshot["findings"][0]["severity"] == "Low"
    assert snapshot["source_hash"] == parsed_csv["source_hash"]
    assert len(snapshot["sources"]) == 2 and snapshot["source_comparison"]
    assert snapshot["coverage"][0]["status"] == "completed"


def test_snapshot_is_detached_and_deterministic():
    parsed = parse_assessment("scan.nessus", nessus(item()), "VA", ["192.0.2.10"])
    snapshot = build_snapshot(parsed, context())
    assert snapshot == build_snapshot(parsed, context())
    parsed["findings"][0]["title"] = "changed externally"
    assert snapshot["findings"][0]["title"] == "Synthetic finding"


def test_bundle_same_snapshot_all_formats_csv_formula_escaped_and_immutable(tmp_path):
    parsed = parse_assessment("scan.csv", csv_input([["1", "192.0.2.1", "High", "=HYPERLINK(\"https://example.test\")", 443, "tcp", '<script>alert(1)</script> 合成說明', "更新設定"]]), "VA", ["192.0.2.1", "192.0.2.2"])
    snapshot = build_snapshot(parsed, context())
    manifest = generate_bundle(snapshot, tmp_path / "bundle")
    assert manifest["statistics"] == snapshot["statistics"]
    assert {item["format"] for item in manifest["artifacts"]} == {"docx", "pdf", "pptx", "xlsx", "csv"}
    for artifact in manifest["artifacts"]:
        content = (tmp_path / "bundle" / artifact["filename"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == artifact["sha256"]
    with (tmp_path / "bundle" / "all.csv").open(encoding="utf-8-sig", newline="") as handle:
        row = list(csv.DictReader(handle))[0]
        assert row["title"].startswith("'=HYPERLINK")
        assert row["snapshot_id"] == snapshot["snapshot_id"]
    book = load_workbook(tmp_path / "bundle" / "summary.xlsx", data_only=False)
    assert book["Findings"]["H2"].data_type == "s"
    assert book["Summary"]["B2"].value == snapshot["snapshot_id"]
    book.close()
    with zipfile.ZipFile(tmp_path / "bundle" / "report.docx") as archive:
        xml = archive.read("word/document.xml").decode()
        assert snapshot["snapshot_id"] in xml and "N/A" in xml
        assert "TOC" in xml and "&lt;script&gt;" in xml
    assert manifest["qa"]["production_ready"] is False
    assert generate_bundle(snapshot, tmp_path / "bundle") == manifest
    (tmp_path / "bundle" / "all.csv").write_text("tampered")
    with pytest.raises(ValueError, match="CHECKSUM"):
        generate_bundle(snapshot, tmp_path / "bundle")


def test_snapshot_mutation_and_production_generation_are_blocked(tmp_path):
    parsed = parse_assessment("scan.nessus", nessus(item()), "VA", ["192.0.2.10"])
    snapshot = build_snapshot(parsed, context())
    mutated = copy.deepcopy(snapshot)
    mutated["statistics"]["occurrence_count"] = 999
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        generate_bundle(mutated, tmp_path / "bad")
    with pytest.raises(ValueError, match="PRODUCTION_TEMPLATE"):
        generate_bundle(build_snapshot(parsed, context(synthetic=False)), tmp_path / "production")
