"""Bounded, offline assessment importers. All supplied evidence remains inert text.

An import is a preview, never a declaration that a scan or review succeeded.
"""

from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import json
import re
from pathlib import PurePosixPath
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

PARSER_VERSION = "kuanguard-parsers/1.0.0"
SCHEMA_VERSION = "1.0"
MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 20000
MAX_TEXT = 50000
SEVERITIES = ("Critical", "High", "Medium", "Low", "Informational", "Unknown")
COVERAGE_STATUSES = {"completed", "not_tested", "failed", "insufficient"}
CHECK_STATUSES = {"passed", "failed", "not_applicable", "not_tested", "insufficient"}
SENSITIVE_QUERY = re.compile(r"token|secret|password|passwd|authorization|api.?key|session|credential", re.I)


class ImportRejected(ValueError):
    pass


def _text(value, limit=MAX_TEXT):
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > limit:
        raise ImportRejected("FIELD_TOO_LARGE: 單一文字欄位超過限制")
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text):
        raise ImportRejected("INVALID_CONTROL_CHARACTER: 文字含不允許控制字元")
    return text


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def normalize_asset(value):
    value = _text(value, 2048)
    if not value:
        raise ImportRejected("MISSING_ASSET: 缺少資產或路徑")
    if "://" in value:
        parsed = urlsplit(value)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise ImportRejected("INVALID_URL: 僅支援 HTTP 或 HTTPS 資產")
        host = parsed.hostname.lower()
        try:
            host = ipaddress.ip_address(host).compressed
        except ValueError:
            pass
        if ":" in host:
            host = f"[{host}]"
        port = parsed.port
        if port and (parsed.scheme, port) not in {("http", 80), ("https", 443)}:
            host += f":{port}"
        return f"{parsed.scheme}://{host}"
    candidate = value.strip("[]")
    try:
        return ipaddress.ip_address(candidate).compressed
    except ValueError:
        # Never split an unbracketed IPv6 address to guess a port.
        match = re.fullmatch(r"\[([^]]+)\]:(\d+)", value)
        if match:
            return ipaddress.ip_address(match.group(1)).compressed
        match = re.fullmatch(r"([^:/]+):(\d+)", value)
        if match:
            return match.group(1).lower().rstrip(".")
        if "\\" in value:
            value = value.replace("\\", "/")
        return value if "/" in value else value.lower().rstrip(".")


def display_location(value):
    """Mask query values and URL userinfo without changing the identity digest."""
    value = _text(value)
    if "://" not in value:
        return value
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    if parsed.port:
        host += f":{parsed.port}"
    query = urlencode([(key, "[REDACTED]" if SENSITIVE_QUERY.search(key) else val)
                       for key, val in parse_qsl(parsed.query, keep_blank_values=True)])
    return urlunsplit((parsed.scheme, host, parsed.path, query, ""))


def _severity(value):
    mapping = {"4": "Critical", "3": "High", "2": "Medium", "1": "Low", "0": "Informational",
               "none": "Informational", "info": "Informational", "informational": "Informational",
               "critical": "Critical", "high": "High", "medium": "Medium", "low": "Low",
               "嚴重": "Critical", "高": "High", "中": "Medium", "低": "Low"}
    return mapping.get(_text(value).lower(), "Unknown")


def _port(value):
    if value in (None, ""):
        return None
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ImportRejected("INVALID_PORT: 連接埠必須是整數") from exc
    if not 0 <= port <= 65535:
        raise ImportRejected("INVALID_PORT: 連接埠超出範圍")
    return port


def _finding(source_id, asset, title, severity, description="", solution="", **extra):
    if not _text(source_id) or not _text(title):
        raise ImportRejected("MISSING_FINDING_ID_OR_TITLE: 缺少來源編號或名稱")
    location = _text(extra.pop("location", ""))
    if extra.get("port") in (None, "") and "://" not in str(asset):
        endpoint = re.fullmatch(r"(?:\[([^]]+)\]|([^:/]+)):(\d+)", str(asset))
        if endpoint:
            extra["port"] = endpoint.group(3)
    result = {"source_id": _text(source_id), "asset": normalize_asset(asset), "title": _text(title),
              "severity": _severity(severity), "description": _text(description), "solution": _text(solution),
              "location": display_location(location), "location_hash": _digest(location), **extra}
    result["port"] = _port(result.get("port"))
    result["protocol"] = _text(result.get("protocol", "")).lower()
    result["evidence"] = _text(result.get("evidence", ""))
    return result


def _coverage(rows, planned_assets, findings):
    result = {normalize_asset(asset): "not_tested" for asset in planned_assets}
    for row in rows:
        if not isinstance(row, dict) or row.get("status") not in COVERAGE_STATUSES:
            raise ImportRejected("INVALID_COVERAGE: 無效範圍紀錄")
        asset = normalize_asset(row.get("asset"))
        result[asset] = row["status"]
    for finding in findings:
        if result.get(finding["asset"], "not_tested") == "not_tested":
            result[finding["asset"]] = "insufficient"
    return [{"asset": asset, "status": status} for asset, status in sorted(result.items())]


def _csv(text, service):
    csv.field_size_limit(MAX_TEXT)
    reader = csv.DictReader(io.StringIO(text, newline=""))
    headers = reader.fieldnames or []
    if len(headers) != len(set(headers)):
        raise ImportRejected("DUPLICATE_CSV_HEADER: CSV 欄名重複")
    required = {"Plugin ID", "Host", "Risk", "Name"} if service == "VA" else {"Issue ID", "URL", "Severity", "Name"}
    if not required.issubset(headers):
        raise ImportRejected("UNSUPPORTED_CSV_SCHEMA: 缺少必要欄位 " + ", ".join(sorted(required - set(headers))))
    findings, coverage = [], []
    for row_number, row in enumerate(reader, 2):
        if row_number > MAX_ROWS + 1:
            raise ImportRejected("TOO_MANY_ROWS: 超過匯入筆數限制")
        if None in row or any(v is None for v in row.values()):
            raise ImportRejected(f"MALFORMED_CSV_ROW: 第 {row_number} 列欄數不符")
        if not any(row.values()):
            continue
        if service == "VA":
            item = _finding(row["Plugin ID"], row["Host"], row["Name"], row["Risk"], row.get("Description", row.get("Synopsis", "")),
                            row.get("Solution", ""), port=row.get("Port"), protocol=row.get("Protocol", ""),
                            evidence=row.get("Plugin Output", ""), cve=_text(row.get("CVE", "")), method="nessus")
        else:
            item = _finding(row["Issue ID"], row["URL"], row["Name"], row["Severity"], row.get("Description", ""),
                            row.get("Solution", ""), location=row["URL"], http_method=_text(row.get("Method", "")).upper(),
                            parameter=_text(row.get("Parameter", "")), method="appscan", evidence=row.get("Evidence", ""))
        findings.append(item)
        # This is a KUANGUARD extension, not a property inferred from Nessus finding rows.
        if row.get("Coverage Status"):
            coverage.append({"asset": item["asset"], "status": row["Coverage Status"]})
    return findings, coverage, {"format": "nessus-csv" if service == "VA" else "wva-all-csv",
                                "coverage_evidence": "explicit Coverage Status column only", "raw_rows": len(findings)}, [
        "CSV 本身僅列發現；未明示 Coverage Status 的資產不視為完整檢測。"]


def _local_name(tag):
    return tag.rsplit("}", 1)[-1]


def _xml(text):
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.I):
        raise ImportRejected("UNSAFE_XML: 禁止 DTD 或外部實體")
    root = SafeET.fromstring(text, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    count = 0
    for element in root.iter():
        count += 1
        if count > MAX_ROWS * 30:
            raise ImportRejected("XML_TOO_COMPLEX: XML 節點超過限制")
        if _local_name(element.tag).lower() in {"script", "iframe", "object", "embed"}:
            raise ImportRejected("ACTIVE_XML_CONTENT: 禁止主動網頁內容")
        element.tag = _local_name(element.tag)
    return root


def _nessus(text):
    root = _xml(text)
    if root.tag != "NessusClientData_v2":
        raise ImportRejected("UNSUPPORTED_NESSUS_SCHEMA: 僅支援 NessusClientData_v2")
    findings, coverage = [], []
    reports = root.findall("Report")
    if not reports:
        raise ImportRejected("MISSING_NESSUS_REPORT: 缺少 Report")
    for host in root.findall("Report/ReportHost"):
        asset = normalize_asset(host.get("name"))
        tags = {tag.get("name"): tag.text or "" for tag in host.findall("HostProperties/tag")}
        status = "completed" if tags.get("HOST_START") and tags.get("HOST_END") else "insufficient"
        if tags.get("scan-status", "").lower() in {"failed", "error", "aborted"}:
            status = "failed"
        coverage.append({"asset": asset, "status": status})
        for item in host.findall("ReportItem"):
            risk = item.findtext("risk_factor")
            if risk is None:
                risk = item.get("severity", "")
            findings.append(_finding(item.get("pluginID"), asset, item.get("pluginName"), risk,
                                     item.findtext("description", ""), item.findtext("solution", ""),
                                     port=item.get("port"), protocol=item.get("protocol", ""),
                                     evidence=item.findtext("plugin_output", ""), cve=", ".join(n.text or "" for n in item.findall("cve")),
                                     method="nessus"))
    return findings, coverage, {"format": "nessus-xml", "source_schema": "NessusClientData_v2",
                                "coverage_evidence": "HOST_START and HOST_END; failed status takes precedence", "raw_rows": len(findings)}, []


def _appscan(text):
    root = _xml(text)
    # Known structure only. A vendor version number alone never enables an unverified layout.
    version = root.get("schemaVersion", "")
    if root.tag != "XmlReport" or version != "kuanguard-appscan-1":
        raise ImportRejected("UNSUPPORTED_APPSCAN_SCHEMA: 原生版本尚待真實樣本驗證；請使用核定 kuanguard-appscan-1 映射 XML 或 WVA all.csv")
    findings = []
    for issue in root.findall("Issues/Issue"):
        url = issue.findtext("Url", "")
        findings.append(_finding(issue.get("IssueTypeID"), url, issue.findtext("Name"), issue.get("Severity"),
                                 issue.findtext("Description", ""), issue.findtext("FixRecommendation", ""),
                                 location=url, http_method=_text(issue.findtext("Method", "")).upper(),
                                 parameter=_text(issue.findtext("Parameter", "")), evidence=issue.findtext("Evidence", ""), method="appscan"))
    coverage = [{"asset": node.get("url"), "status": node.get("status")} for node in root.findall("Coverage/Target")]
    return findings, coverage, {"format": "appscan-mapped-xml", "source_schema": version,
                                "vendor_version": _text(root.get("productVersion", "unknown")), "raw_rows": len(findings),
                                "native_appscan_compatibility": "pending_real_vendor_fixture"}, [
        "AppScan 僅支援明確的 KUANGUARD 映射 profile；未宣稱原生 HCL 或 IBM XML 版本已完成相容驗證。"]


def _json(text):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ImportRejected("DUPLICATE_JSON_KEY: JSON 欄位重複")
            result[key] = value
        return result
    value = json.loads(text, object_pairs_hook=unique_object, parse_constant=lambda _: (_ for _ in ()).throw(ImportRejected("INVALID_JSON_NUMBER")))
    if not isinstance(value, dict):
        raise ImportRejected("INVALID_JSON_SCHEMA: 根節點必須是物件")
    return value


def _shc(text):
    data = _json(text)
    if data.get("schema") != "kuanguard.shc/1" or not data.get("checklist_version") or not isinstance(data.get("checks"), list):
        raise ImportRejected("UNSUPPORTED_SHC_SCHEMA: 需要 kuanguard.shc/1、checklist_version 與 checks")
    findings, warnings, coverage = [], [], list(data.get("coverage", []))
    for check in data["checks"]:
        if not isinstance(check, dict) or check.get("status") not in CHECK_STATUSES:
            raise ImportRejected("INVALID_CHECK_STATUS: 無效健診判定")
        status = check["status"]
        evidence = _text(check.get("evidence", ""))
        if status in {"passed", "failed"} and (not evidence or "expected" not in check or "observed" not in check or not _text(check.get("reviewer"))):
            status = "insufficient"
            warnings.append(f"檢核 {_text(check.get('id'))} 缺預期值、觀測值、證據或覆核者，判為證據不足。")
        if status == "not_applicable" and not _text(check.get("applicability_reason")):
            status = "insufficient"
            warnings.append(f"檢核 {_text(check.get('id'))} 缺不適用理由，判為證據不足。")
        finding = _finding(check.get("id"), check.get("asset"), check.get("title"), check.get("severity"),
                           check.get("description", ""), check.get("solution", ""), evidence=evidence,
                           check_status=status, expected=_text(check.get("expected")), observed=_text(check.get("observed")),
                           reviewer=_text(check.get("reviewer")), applicability_reason=_text(check.get("applicability_reason")),
                           rule_id=_text(check.get("id")), method="shc")
        findings.append(finding)
    for asset in {f["asset"] for f in findings}:
        statuses = {f["check_status"] for f in findings if f["asset"] == asset}
        state = "insufficient" if "insufficient" in statuses else "not_tested" if "not_tested" in statuses else "completed"
        # Item evidence can lower a caller's claimed coverage, never silently raise it.
        declared = next((r.get("status") for r in coverage if normalize_asset(r.get("asset")) == asset), None)
        if declared is None and state == "completed":
            state = "insufficient"
        if state != "completed" or declared is None:
            coverage = [r for r in coverage if normalize_asset(r.get("asset")) != asset]
            coverage.append({"asset": asset, "status": state})
    return findings, coverage, {"format": "shc-json", "checklist_version": _text(data["checklist_version"]),
                                "raw_rows": len(findings)}, warnings


def _pt(text):
    data = _json(text)
    if data.get("schema") != "kuanguard.pt/1" or not isinstance(data.get("findings"), list):
        raise ImportRejected("UNSUPPORTED_PT_SCHEMA: 需要 kuanguard.pt/1 與 findings")
    required = ("authorization_reference", "methodology", "test_window", "stop_conditions")
    if any(not data.get(key) for key in required):
        raise ImportRejected("MISSING_PT_SCOPE: 缺少授權、方法、測試時段或停止條件")
    findings, warnings = [], []
    for finding in data["findings"]:
        reviewed = finding.get("reviewed") is True and bool(finding.get("reviewer"))
        if not reviewed:
            warnings.append(f"PT 發現 {_text(finding.get('id'))} 尚未人工覆核，不能核定或發布。")
        findings.append(_finding(finding.get("id"), finding.get("asset"), finding.get("title"), finding.get("severity"),
                                 finding.get("description", ""), finding.get("solution", ""), location=finding.get("location", ""),
                                 evidence=finding.get("evidence", ""), reviewed=reviewed, reviewer=_text(finding.get("reviewer")),
                                 preconditions=_text(finding.get("preconditions")), reproduction=_text(finding.get("reproduction")),
                                 impact=_text(finding.get("impact")), risk_reason=_text(finding.get("risk_reason")),
                                 method=_text(data["methodology"])))
    return findings, data.get("coverage", []), {"format": "pt-json", "raw_rows": len(findings),
                                               **{key: _text(data[key]) for key in required}}, warnings


def _sarif(text):
    data = _json(text)
    if data.get("version") != "2.1.0" or not isinstance(data.get("runs"), list) or not data["runs"]:
        raise ImportRejected("UNSUPPORTED_SARIF_SCHEMA: 僅支援 SARIF 2.1.0 runs")
    findings, coverage, tools, disabled, excluded, warnings, provenance = [], [], [], [], [], [], []
    for run in data["runs"]:
        driver = run.get("tool", {}).get("driver", {})
        if not driver.get("name"):
            raise ImportRejected("MISSING_SARIF_TOOL: SARIF 缺工具名稱")
        tools.append({"name": _text(driver["name"]), "version": _text(driver.get("version", "unknown"))})
        for source in run.get("versionControlProvenance", []):
            provenance.append({"repository_uri": display_location(source.get("repositoryUri", "")),
                               "commit": _text(source.get("revisionId", "")), "branch": _text(source.get("branch", ""))})
        rules = {rule.get("id"): rule for rule in driver.get("rules", [])}
        disabled.extend(rule_id for rule_id, rule in rules.items() if rule.get("defaultConfiguration", {}).get("enabled") is False)
        properties = run.get("properties", {}).get("kuanguard", {})
        excluded.extend(_text(path) for path in properties.get("excluded_paths", []))
        invocations = run.get("invocations", [])
        completed = bool(invocations) and all(item.get("executionSuccessful") is True for item in invocations)
        for path in properties.get("covered_paths", []):
            coverage.append({"asset": _text(path), "status": "completed" if completed else "failed"})
        for result in run.get("results", []):
            rule_id = result.get("ruleId")
            if not rule_id and isinstance(result.get("ruleIndex"), int):
                index = result["ruleIndex"]
                entries = driver.get("rules", [])
                if not 0 <= index < len(entries):
                    raise ImportRejected("INVALID_SARIF_RULE_INDEX")
                rule_id = entries[index].get("id")
            rule = rules.get(rule_id, {})
            security_score = result.get("properties", {}).get("security-severity", rule.get("properties", {}).get("security-severity"))
            if security_score is not None:
                score = float(security_score)
                if not 0 <= score <= 10:
                    raise ImportRejected("INVALID_SECURITY_SEVERITY")
                severity = "Critical" if score >= 9 else "High" if score >= 7 else "Medium" if score >= 4 else "Low" if score > 0 else "Informational"
            else:
                severity = {"error": "High", "warning": "Medium", "note": "Informational", "none": "Informational"}.get(
                    result.get("level", rule.get("defaultConfiguration", {}).get("level", "warning")), "Unknown")
            locations = result.get("locations", [])
            if not locations:
                raise ImportRejected("MISSING_SARIF_LOCATION: 無法將來源發現關聯範圍")
            for location in locations:
                physical = location.get("physicalLocation", {})
                uri = physical.get("artifactLocation", {}).get("uri", "")
                if not uri:
                    index = physical.get("artifactLocation", {}).get("index")
                    artifacts = run.get("artifacts", [])
                    if isinstance(index, int) and 0 <= index < len(artifacts):
                        uri = artifacts[index].get("location", {}).get("uri", "")
                if not uri or "://" in uri or PurePosixPath(uri.replace("\\", "/")).is_absolute() or ".." in PurePosixPath(uri.replace("\\", "/")).parts:
                    raise ImportRejected("UNSAFE_SOURCE_PATH: 只接受相對來源路徑，不抓取網址或讀取主機檔案")
                region = physical.get("region", {})
                fingerprint = result.get("partialFingerprints") or result.get("fingerprints") or {}
                is_secret = "secret" in str(rule_id).lower() or any("secret" in str(tag).lower() for tag in rule.get("properties", {}).get("tags", []))
                message = "Secrets 發現內容已遮罩，請於授權來源工具檢視。" if is_secret else result.get("message", {}).get("text", "")
                findings.append(_finding(rule_id, uri, rule.get("shortDescription", {}).get("text") or rule.get("name") or rule_id,
                                         severity, message, rule.get("help", {}).get("text", ""), location=uri,
                                         rule_id=_text(rule_id), line=region.get("startLine"), column=region.get("startColumn"),
                                         source_fingerprint=_digest(fingerprint) if fingerprint else "", snippet="[REDACTED]" if is_secret else "",
                                         method="sarif:" + _text(driver["name"]), suppressed=bool(result.get("suppressions"))))
        if not properties.get("covered_paths"):
            warnings.append("SARIF 未提供 kuanguard.covered_paths；未從零發現或工具成功推論路徑已覆蓋。")
    return findings, coverage, {"format": "sarif", "source_schema": "2.1.0", "tools": tools,
                                "disabled_rules": sorted(set(disabled)), "excluded_paths": sorted(set(excluded)),
                                "raw_rows": len(findings), "source_execution": "never", "version_control": provenance,
                                "subservices": ["SAST result import"]}, warnings


def parse_assessment(filename: str, content: bytes, service_code: str, planned_assets: list[str]) -> dict:
    """Return an auditable preview. Invalid input returns errors with no partial data."""
    result = {"schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION,
              "source_hash": hashlib.sha256(content).hexdigest(), "findings": [], "coverage": [],
              "errors": [], "warnings": [], "metadata": {"source_bytes": len(content), "service_code": service_code}}
    try:
        if len(content) > MAX_BYTES:
            raise ImportRejected("FILE_TOO_LARGE: 單檔限制 10 MiB")
        if not content:
            raise ImportRejected("EMPTY_FILE: 檔案是空的")
        if content.startswith((b"PK\x03\x04", b"PK\x05\x06", b"\x1f\x8b", b"MZ")):
            raise ImportRejected("UNSUPPORTED_ARCHIVE_OR_EXECUTABLE: 不接受壓縮、Office 巨集或執行檔")
        if len(planned_assets) > MAX_ROWS:
            raise ImportRejected("TOO_MANY_ASSETS")
        suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
        text = content.decode("utf-8-sig", errors="strict")
        routes = {("VA", ".csv"): lambda: _csv(text, "VA"), ("VA", ".nessus"): lambda: _nessus(text),
                  ("WVA", ".csv"): lambda: _csv(text, "WVA"), ("WVA", ".xml"): lambda: _appscan(text),
                  ("WEBVA", ".csv"): lambda: _csv(text, "WVA"), ("WEBVA", ".xml"): lambda: _appscan(text),
                  ("SHC", ".json"): lambda: _shc(text), ("PT", ".json"): lambda: _pt(text),
                  ("SOURCE", ".sarif"): lambda: _sarif(text), ("SOURCE", ".json"): lambda: _sarif(text)}
        if (service_code, suffix) not in routes:
            raise ImportRejected("UNSUPPORTED_FORMAT: 服務與檔案格式不相容")
        findings, rows, metadata, warnings = routes[(service_code, suffix)]()
        if len(findings) > MAX_ROWS:
            raise ImportRejected("TOO_MANY_FINDINGS")
        unique, duplicates = {}, []
        for finding in findings:
            identity = [finding["asset"], finding["source_id"], finding.get("port"), finding.get("protocol"),
                        finding["location_hash"], finding.get("http_method"), finding.get("parameter"),
                        finding.get("source_fingerprint"), finding.get("method"),
                        None if finding.get("source_fingerprint") else finding.get("line"),
                        None if finding.get("source_fingerprint") else finding.get("column")]
            fingerprint = _digest(identity)
            finding["fingerprint"] = fingerprint
            if fingerprint in unique:
                if unique[fingerprint]["severity"] != finding["severity"]:
                    raise ImportRejected("CONFLICTING_DUPLICATE: 相同發現識別有不同風險，需明確解決後匯入")
                duplicates.append({"fingerprint": fingerprint, "source_id": finding["source_id"], "reason": "same occurrence identity"})
            else:
                unique[fingerprint] = finding
            if finding["severity"] == "Unknown":
                warnings.append(f"來源 {finding['source_id']} 缺少可識別嚴重度，保留 Unknown。")
        result.update(findings=list(unique.values()), coverage=_coverage(rows, planned_assets, findings), warnings=sorted(set(warnings)))
        result["metadata"].update(metadata, valid_rows=len(unique), duplicate_rows=len(duplicates), duplicate_audit=duplicates,
                                   planned_assets=sorted({normalize_asset(a) for a in planned_assets}))
    except (ImportRejected, DefusedXmlException, SafeET.ParseError, UnicodeDecodeError, csv.Error, json.JSONDecodeError,
            ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        # Do not put input data or Python tracebacks into the import preview.
        message = str(exc) if isinstance(exc, ImportRejected) else "MALFORMED_INPUT: 格式或資料型別無效"
        result["errors"] = [message]
        result["findings"], result["coverage"] = [], []
    return result
