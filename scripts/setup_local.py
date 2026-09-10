"""Create only development secrets, without printing them or replacing existing configuration."""
from pathlib import Path
import secrets


def main():
    root = Path(__file__).resolve().parents[1]
    path = root / ".env"
    if path.exists():
        print("Existing .env preserved")
        return
    owner = secrets.token_urlsafe(32)
    app = secrets.token_urlsafe(32)
    template = (root / ".env.example").read_text(encoding="utf-8")
    template = template.replace("kuanguard:CHANGE_LOCALLY", f"kuanguard:{app}")
    template = template.replace("PAYMENT_WEBHOOK_SECRET=\n", f"PAYMENT_WEBHOOK_SECRET={secrets.token_urlsafe(48)}\n")
    template += f"\nPOSTGRES_OWNER_PASSWORD={owner}\nPOSTGRES_APP_PASSWORD={app}\n"
    template += f"MIGRATION_DATABASE_URL=postgresql+psycopg://kuanguard_owner:{owner}@127.0.0.1:55438/kuanguard\n"
    path.write_text(template, encoding="utf-8")
    (root / ".local").mkdir(exist_ok=True)
    print("Development .env created; credentials not displayed")


if __name__ == "__main__":
    main()
