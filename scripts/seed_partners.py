"""Explicit, additive local fixture; never changes existing customer IDs or balances."""
from pathlib import Path
import sys
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / ".env")
from kuanguard.db import engine  # noqa: E402
from kuanguard.partner_setup import seed_partners  # noqa: E402

if __name__ == "__main__":
    with engine().begin() as conn:
        print(seed_partners(conn))
