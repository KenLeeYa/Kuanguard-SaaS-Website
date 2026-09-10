"""Create only development secrets, without printing them or replacing existing configuration."""
from pathlib import Path
import secrets


def main():
    root = Path(__file__).resolve().parents[1]
    path = root / ".env"
    if path.exists():
        from dotenv import dotenv_values
        values = dotenv_values(path)
        if values.get("APP_ENV", "development") == "development" and not values.get("PORTAL_PROXY_SECRET"):
            with path.open("a", encoding="utf-8") as stream:
                stream.write(f"\nPORTAL_PROXY_SECRET={secrets.token_urlsafe(48)}\n")
            print("Existing settings preserved; added private local BFF signing key")
        else:
            print("Existing .env preserved")
        return
    owner = secrets.token_urlsafe(32)
    app = secrets.token_urlsafe(32)
    template = (root / ".env.example").read_text(encoding="utf-8")
    template = template.replace("kuanguard:CHANGE_LOCALLY", f"kuanguard:{app}")
    template = template.replace("PAYMENT_WEBHOOK_SECRET=\n", f"PAYMENT_WEBHOOK_SECRET={secrets.token_urlsafe(48)}\n")
    template = template.replace("PORTAL_PROXY_SECRET=\n", f"PORTAL_PROXY_SECRET={secrets.token_urlsafe(48)}\n")
    template += f"\nPOSTGRES_OWNER_PASSWORD={owner}\nPOSTGRES_APP_PASSWORD={app}\n"
    template += f"MIGRATION_DATABASE_URL=postgresql+psycopg://kuanguard_owner:{owner}@127.0.0.1:55438/kuanguard\n"
    path.write_text(template, encoding="utf-8")
    (root / ".local").mkdir(exist_ok=True)
    print("Development .env created; credentials not displayed")


if __name__ == "__main__":
    main()
