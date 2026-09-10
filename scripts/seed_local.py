"""Install development fixtures only when absent; never reset an existing tenant."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from kuanguard.db import engine  # noqa: E402
from kuanguard.seed import seed, seed_owner_increment  # noqa: E402


if __name__ == "__main__":
    with engine().begin() as conn:
        print(seed(conn)["status"])
        print(seed_owner_increment(conn)["status"])
