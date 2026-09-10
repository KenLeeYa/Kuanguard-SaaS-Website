from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    app_env: str = "development"
    product_id: str = "kuanguard"
    deployment_surface: str = "local"
    resource_product_id: str = "kuanguard"
    supabase_project_ref: str = ""
    expected_supabase_project_ref: str = ""
    access_issuer: str = ""
    access_audience: str = ""
    company_apex_domain: str = "kuanguard.com"
    brand_name: str = "KUANGUARD"
    business_timezone: str = "Asia/Taipei"
    database_url: str = "sqlite:///.local/kuanguard.db"
    redis_url: str = ""
    allowed_origins: str = "http://127.0.0.1:3180,http://localhost:3180,http://127.0.0.1:8180"
    local_data_dir: Path = Path(".local/storage")
    auth_provider: str = "development"
    storage_provider: str = "local"
    payment_provider: str = "sandbox"
    mail_provider: str = "disabled"
    gophish_provider: str = "disabled"
    stream_provider: str = "disabled"
    ai_provider: str = "disabled"
    production_release_approved: bool = False
    payment_webhook_secret: str = Field(default="", repr=False)
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = Field(default="", repr=False)
    oidc_redirect_uri: str = ""
    r2_endpoint: str = ""
    r2_access_key_id: str = Field(default="", repr=False)
    r2_secret_access_key: str = Field(default="", repr=False)
    r2_private_bucket: str = ""
    max_import_bytes: int = 5_000_000
    session_hours: int = 8
    public_site_url: str = "https://kuanguard.com"
    customer_app_url: str = "https://app.kuanguard.com"
    internal_app_url: str = "https://admin.kuanguard.com"
    partner_portal_url: str = "https://partner.kuanguard.com"
    central_auth_url: str = "https://auth.kuanguard.com"
    custom_domain_target: str = ""
    merchant_entry_url: str = "https://app.qidaigo.com/login"
    portal_proxy_secret: str = Field(default="", repr=False)

    @model_validator(mode="after")
    def validate_environment(self):
        from urllib.parse import urlsplit
        for name in ("public_site_url", "customer_app_url", "internal_app_url", "partner_portal_url", "central_auth_url"):
            value = urlsplit(getattr(self, name))
            if (value.scheme != "https" or not value.hostname or value.username or value.password
                    or value.path not in {"", "/"} or value.query or value.fragment or value.port
                    or not (value.hostname == self.company_apex_domain or value.hostname.endswith("." + self.company_apex_domain))):
                raise ValueError(f"{name} must be an exact HTTPS origin within the configured platform domain")
        merchant = urlsplit(self.merchant_entry_url)
        if (merchant.scheme != "https" or merchant.username or merchant.password or merchant.fragment
                or merchant.query or merchant.hostname not in {"app.qidaigo.com", "app.kuanguard.com"}):
            raise ValueError("Merchant entry must be an approved existing product login URL")
        if self.product_id != "kuanguard" or self.resource_product_id != "kuanguard":
            raise ValueError("Cross-product resource binding denied")
        if self.company_apex_domain != "kuanguard.com":
            raise ValueError("KUANGUARD requires kuanguard.com; another product domain is prohibited")
        if self.supabase_project_ref and self.supabase_project_ref != self.expected_supabase_project_ref:
            raise ValueError("Supabase project identity mismatch")
        foreign_projects = {"eyuctbnlvnbnivwasvqr", "daeqwtpaxcebmtwxqdkj", "dfuhylsmhrysbmhpeylx"}
        if self.supabase_project_ref in foreign_projects or any(project in self.database_url for project in foreign_projects):
            raise ValueError("Existing other-product database is prohibited")
        if "supabase.co" in self.database_url or "pooler.supabase.com" in self.database_url:
            if not self.supabase_project_ref or self.supabase_project_ref not in self.database_url:
                raise ValueError("Database URL is not bound to the verified KUANGUARD Supabase project")
        if self.deployment_surface not in {"local", "public", "internal"}:
            raise ValueError("Invalid DEPLOYMENT_SURFACE")
        if self.app_env not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test or production")
        if self.app_env == "production":
            failures = []
            if not self.database_url.startswith("postgresql+"):
                failures.append("PostgreSQL required")
            if self.auth_provider != "oidc" or not all(
                [self.oidc_issuer, self.oidc_client_id, self.oidc_client_secret, self.oidc_redirect_uri]
            ):
                failures.append("verified OIDC configuration required")
            if self.payment_provider == "sandbox" or self.storage_provider == "local":
                failures.append("development adapters prohibited")
            if not self.production_release_approved:
                failures.append("production release evidence not approved")
            # Provider enablement cannot turn an unfinished integration into production readiness.
            failures.append("seven-service production acceptance and provider integrations pending; see release-readiness")
            raise ValueError("Production gate closed: " + "; ".join(failures))
        return self

    @property
    def origins(self):
        return {origin.strip().rstrip("/") for origin in self.allowed_origins.split(",") if origin.strip()}


@lru_cache
def settings() -> Settings:
    return Settings()
