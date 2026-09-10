"""Export the actual API contract; contains schemas only, never runtime data or secrets."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from kuanguard.api import app  # noqa: E402


def main():
    target = ROOT / "docs/openapi.json"
    contract = json.dumps(app.openapi(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if "--check" in sys.argv:
        if not target.exists() or target.read_text(encoding="utf-8") != contract:
            raise SystemExit("OpenAPI export is stale: run scripts/export_openapi.py")
    else:
        target.write_text(contract, encoding="utf-8")
    print(f"OpenAPI verified: {len(app.openapi()['paths'])} paths")


if __name__ == "__main__":
    main()
