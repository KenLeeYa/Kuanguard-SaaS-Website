"""Read final sample bundles and render evidence; write a machine-readable receipt."""

from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import platform
import importlib.metadata
import sys
import zipfile

from openpyxl import load_workbook
from pypdf import PdfReader
from pptx import Presentation

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parents[1] / "backend"))
from kuanguard.reports import _verify_snapshot


def main():
    rows = []
    for directory in sorted((BASE / "bundles_final").iterdir()):
        if not directory.is_dir():
            continue
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        snapshot = json.loads((directory / "snapshot.json").read_text(encoding="utf-8"))
        _verify_snapshot(snapshot)
        assert manifest["snapshot_hash"] == snapshot["snapshot_hash"]
        assert manifest["statistics"] == snapshot["statistics"]
        for artifact in manifest["artifacts"]:
            assert hashlib.sha256((directory / artifact["filename"]).read_bytes()).hexdigest() == artifact["sha256"]
        with (directory / "all.csv").open(encoding="utf-8-sig", newline="") as source:
            csv_rows = list(csv.DictReader(source))
        assert len(csv_rows) == len(snapshot["findings"])
        assert all(row["snapshot_id"] == snapshot["snapshot_id"] and row["synthetic"] == "True" for row in csv_rows)
        risk_rows = [r for r in csv_rows if r["severity"] in ("Critical", "High", "Medium", "Low") and (snapshot["service_code"] != "SHC" or r["check_status"] == "failed")]
        counts = Counter(r["severity"] for r in risk_rows)
        assert {level: counts[level] for level in ("Critical", "High", "Medium", "Low")} == manifest["statistics"]["severity_counts"]
        book = load_workbook(directory / "summary.xlsx", data_only=False)
        assert book["Summary"]["B2"].value == snapshot["snapshot_id"]
        assert book["Findings"].max_row == len(csv_rows) + 1
        assert [book["Summary"].cell(row, 2).value for row in range(6, 10)] == [counts[level] for level in ("Critical", "High", "Medium", "Low")]
        assert not any(cell.data_type == "f" for sheet in book for row in sheet for cell in row)
        book.close()
        with zipfile.ZipFile(directory / "report.docx") as archive:
            docxml = archive.read("word/document.xml").decode()
            assert snapshot["snapshot_id"] in docxml and "TOC" in docxml and "標楷體" in docxml
            assert "PAGE" in archive.read("word/footer1.xml").decode()
        pdf = PdfReader(directory / "report.pdf")
        pdf_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        assert snapshot["snapshot_id"] in pdf_text and "N/A" in pdf_text
        assert all((page.extract_text() or "").strip() for page in pdf.pages)
        renders = list((BASE / "qa_final" / directory.name).glob("page-*.png"))
        assert len(renders) == len(pdf.pages)
        deck = Presentation(directory / "summary.pptx")
        assert all(snapshot["snapshot_id"] in "\n".join(shape.text for shape in slide.shapes if shape.has_text_frame) for slide in deck.slides)
        rows.append({"sample": directory.name, "snapshot_id": snapshot["snapshot_id"], "snapshot_hash": snapshot["snapshot_hash"],
                     "artifacts_verified": len(manifest["artifacts"]), "pdf_pages": len(pdf.pages), "slide_count": len(deck.slides),
                     "rendered_page_count": len(renders), "csv_rows": len(csv_rows), "statistics": manifest["statistics"]["severity_counts"],
                     "checksums": "pass", "snapshot_and_counts": "pass", "no_excel_formulas": "pass",
                     "pdf_visual_review": "all_pages_inspected_no_clipping_or_missing_glyphs",
                     "office_visual_review": "not_performed_bundled_libreoffice_unavailable", "production_ready": False})
    result = {"qa_schema": "kuanguard.sample-qa/1", "date": "2026-09-10", "runtime": platform.python_version(),
              "libraries": {name: importlib.metadata.version(name) for name in ("python-docx", "python-pptx", "reportlab", "openpyxl", "pypdf", "defusedxml")},
              "samples": rows, "pdf_pages_reviewed": sum(row["pdf_pages"] for row in rows), "production_ready": False,
              "limits": ["合成樣本，不是工具對真實資產的測試結果", "尚無正式核准模板", "DOCX 目錄與 PPTX 實際 Office 全頁渲染尚未驗證", "字型容器散布權未核定"]}
    destination = BASE / "qa_final/verification.json"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"samples": len(rows), "pdf_pages_reviewed": result["pdf_pages_reviewed"], "checks": "pass", "receipt": str(destination)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
