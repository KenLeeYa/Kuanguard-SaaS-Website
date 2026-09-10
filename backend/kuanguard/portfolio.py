"""Read-only portfolio summaries. Never connect to another product's database."""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import hmac
import ipaddress
import json
import secrets
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx
import jwt
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, MetaData, String, Table, UniqueConstraint, func, select

from . import models as m
from .config import settings as app_settings
from .db import add, aware, change, one

PORTFOLIO_SCOPE = "portfolio.summary.read"
MAX_RESPONSE_BYTES = 128 * 1024
PRODUCTS = {"kuanguard": "KUANGUARD 資安服務", "qidaigo": "QIDAIGO 訂餐服務"}

# Separate minimal projections share KUANGUARD's tenant boundary and RLS registry.
portfolio_metadata = MetaData(naming_convention=m.metadata.naming_convention)
connectors = Table("portfolio_connectors", portfolio_metadata,
                     Column("id", String(36), primary_key=True, default=m.uid),
                     Column("created_at", DateTime(timezone=True), nullable=False, default=m.now),
                     Column("tenant_id", String(36), ForeignKey(m.tenants.c.id), nullable=False, index=True),
                     m.col("product", String(32)), m.col("environment", String(32)),
                     m.col("status", String(32), default="disconnected"), m.col("grant_binding", String(64)),
                     m.col("projection", JSON), m.col("source_at", DateTime(timezone=True)),
                     m.col("synced_at", DateTime(timezone=True)), m.col("expires_at", DateTime(timezone=True)),
                     m.col("generation", Integer, default=0), m.col("error_code", String(80)),
                     UniqueConstraint("tenant_id", "product", "environment"), UniqueConstraint("tenant_id", "id"))
PORTFOLIO_TABLES = (connectors,)
if connectors.name not in m.TENANT_TABLES:
    m.TENANT_TABLES.append(connectors.name)


class PortfolioSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="portfolio_", extra="ignore")
    environment: Literal["development", "test", "staging", "production"] = "development"
    cache_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    source_max_age_seconds: int = Field(default=900, ge=30, le=86400)
    timeout_seconds: float = Field(default=2, ge=0.1, le=5)
    qidaigo_url: str = ""
    qidaigo_allowed_hosts: str = ""
    qidaigo_tenant_scope: str = ""
    qidaigo_owner_tenant_id: str = ""
    qidaigo_token: SecretStr = SecretStr("")
    qidaigo_token_key: SecretStr = SecretStr("")
    qidaigo_response_key: SecretStr = SecretStr("")
    qidaigo_deep_link: str = ""

    @model_validator(mode="after")
    def url_boundary(self):
        for secret in (self.qidaigo_token_key, self.qidaigo_response_key):
            if secret.get_secret_value() and len(secret.get_secret_value()) < 32:
                raise ValueError("Portfolio signing keys require at least 32 characters")
        for value in (self.qidaigo_url, self.qidaigo_deep_link):
            if not value:
                continue
            parsed = urlsplit(value)
            hosts = {host.strip().lower() for host in self.qidaigo_allowed_hosts.split(",") if host.strip()}
            if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() not in hosts or parsed.username or parsed.password or parsed.fragment or parsed.query or parsed.port not in (None, 443):
                raise ValueError("QIDAIGO URL must use HTTPS and an exact approved host, without query/userinfo/redirect aliases")
            if parsed.hostname.lower() in {"localhost", "metadata.google.internal"} or parsed.hostname.lower().endswith((".localhost", ".internal")):
                raise ValueError("Private/internal source hosts are prohibited")
            try:
                address = ipaddress.ip_address(parsed.hostname)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                raise ValueError("Private source addresses are prohibited")
        return self


@lru_cache
def portfolio_settings():
    return PortfolioSettings()


class ConnectorError(Exception):
    def __init__(self, code, state="error"):
        self.code, self.state = code, state
        super().__init__(code)


class Metric(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    key: str
    value: int | None = Field(ge=0)
    unit: Literal["minor_currency", "points", "count"]
    currency: str | None
    tax_basis: Literal["inclusive", "exclusive", "not_applicable", "unknown"]
    definition_version: str
    period_start: str
    period_end: str
    timezone: str
    measurement: Literal["flow", "balance"] = "flow"
    verified: bool

    @field_validator("period_start", "period_end")
    @classmethod
    def aware_time(cls, value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Metric times require an offset")
        return value

    @model_validator(mode="after")
    def consistent(self):
        try:
            ZoneInfo(self.timezone)
        except (KeyError, ValueError) as exc:
            raise ValueError("Metric timezone is invalid") from exc
        start = datetime.fromisoformat(self.period_start.replace("Z", "+00:00"))
        end = datetime.fromisoformat(self.period_end.replace("Z", "+00:00"))
        if end < start:
            raise ValueError("Metric period is reversed")
        if self.unit == "minor_currency" and (not self.currency or len(self.currency) != 3 or not self.currency.isupper()):
            raise ValueError("Financial metrics require an ISO currency")
        if self.unit != "minor_currency" and (self.currency is not None or self.tax_basis != "not_applicable"):
            raise ValueError("Point/count metrics cannot claim currency or tax basis")
        return self


class SourceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["portfolio.summary/1"]
    product: Literal["qidaigo"]
    environment: Literal["development", "test", "staging", "production"]
    scope: Literal["portfolio.summary.read"]
    tenant_scope: str
    grant_id: str
    source_at: str
    complete: bool
    synthetic: bool
    metrics: list[Metric] = Field(max_length=20)
    health: Literal["healthy", "degraded", "unknown"]
    tasks_open: int | None = Field(ge=0)
    tasks_overdue: int | None = Field(ge=0)


QIDAIGO_METRICS = {"gmv": "訂餐 GMV（非平台收入）", "platform_fees_accrued": "平台應計服務費",
                   "platform_fees_received": "平台實收服務費", "refunds": "訂單交易退款額"}


def credential_binding(config, owner_tenant_id, now=None):
    now = now or m.now()
    required = [config.qidaigo_url, config.qidaigo_tenant_scope, config.qidaigo_owner_tenant_id,
                config.qidaigo_token.get_secret_value(), config.qidaigo_token_key.get_secret_value(), config.qidaigo_response_key.get_secret_value()]
    if not all(required):
        raise ConnectorError("SOURCE_NOT_CONFIGURED", "disconnected")
    if owner_tenant_id != config.qidaigo_owner_tenant_id:
        raise ConnectorError("SOURCE_SCOPE_NOT_GRANTED", "disconnected")
    try:
        claims = jwt.decode(config.qidaigo_token.get_secret_value(), config.qidaigo_token_key.get_secret_value(), algorithms=["HS256"],
                            audience="kuanguard-portfolio", issuer="qidaigo-summary",
                            options={"require": ["exp", "iat", "jti", "sub"], "verify_exp": False, "verify_iat": False})
        if not isinstance(claims["exp"], (float, int)) or not isinstance(claims["iat"], (float, int)) or claims["exp"] <= now.timestamp() or claims["iat"] > now.timestamp() + 30:
            raise ConnectorError("CREDENTIAL_EXPIRED_OR_FUTURE", "revoked")
        if claims.get("product") != "qidaigo" or claims.get("environment") != config.environment or claims.get("scope") != PORTFOLIO_SCOPE or claims.get("tenant_scope") != config.qidaigo_tenant_scope:
            raise ConnectorError("CREDENTIAL_BINDING_MISMATCH", "revoked")
        if claims.get("sub") != "portfolio-readonly" or not isinstance(claims.get("jti"), str) or len(claims["jti"]) > 120:
            raise ConnectorError("CREDENTIAL_BINDING_MISMATCH", "revoked")
        binding = hashlib.sha256(json.dumps({"owner_tenant": owner_tenant_id, "product": "qidaigo", "environment": config.environment,
                                             "scope": config.qidaigo_tenant_scope, "grant": claims["jti"]}, sort_keys=True).encode()).hexdigest()
        return claims, binding
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError) as exc:
        if isinstance(exc, ConnectorError):
            raise
        raise ConnectorError("CREDENTIAL_INVALID", "revoked") from exc


def fetch_qidaigo(config, owner_tenant_id, *, now=None, transport=None):
    """One bounded GET to a statically approved HTTPS endpoint; no redirects."""
    now = now or m.now()
    claims, binding = credential_binding(config, owner_tenant_id, now)
    nonce = secrets.token_urlsafe(24)
    try:
        with httpx.Client(timeout=config.timeout_seconds, follow_redirects=False, trust_env=False, transport=transport) as client:
            with client.stream("GET", config.qidaigo_url, headers={"Authorization": "Bearer " + config.qidaigo_token.get_secret_value(),
                              "Accept": "application/json", "X-Portfolio-Nonce": nonce}) as response:
                if response.status_code in (401, 403):
                    raise ConnectorError("SOURCE_AUTH_REVOKED", "revoked")
                if response.status_code != 200:
                    raise ConnectorError("SOURCE_HTTP_ERROR")
                if response.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
                    raise ConnectorError("SOURCE_CONTENT_TYPE")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise ConnectorError("SOURCE_RESPONSE_TOO_LARGE")
                timestamp = response.headers.get("x-portfolio-timestamp", "")
                try:
                    timestamp_value = int(timestamp)
                except ValueError as exc:
                    raise ConnectorError("SOURCE_SIGNATURE_INVALID") from exc
                if abs(now.timestamp() - timestamp_value) > 60:
                    raise ConnectorError("SOURCE_SIGNATURE_EXPIRED")
                signed = timestamp.encode() + b"\n" + nonce.encode() + b"\n" + bytes(body)
                expected = hmac.new(config.qidaigo_response_key.get_secret_value().encode(), signed, hashlib.sha256).hexdigest()
                if not hmac.compare_digest(expected, response.headers.get("x-portfolio-signature", "")):
                    raise ConnectorError("SOURCE_SIGNATURE_INVALID")
        source = SourceSummary.model_validate_json(bytes(body))
        if source.environment != config.environment or source.tenant_scope != config.qidaigo_tenant_scope or source.grant_id != claims["jti"]:
            raise ConnectorError("SOURCE_BINDING_MISMATCH")
        if source.synthetic and config.environment == "production":
            raise ConnectorError("PRODUCTION_SYNTHETIC_SOURCE_REJECTED")
        source_at = datetime.fromisoformat(source.source_at.replace("Z", "+00:00"))
        if source_at.tzinfo is None or source_at > now + timedelta(seconds=60):
            raise ConnectorError("SOURCE_TIME_INVALID")
        if source_at < now - timedelta(seconds=config.source_max_age_seconds):
            raise ConnectorError("SOURCE_STALE", "stale")
        identities = set()
        metrics = []
        for metric in source.metrics:
            if metric.key not in QIDAIGO_METRICS or metric.definition_version != f"qidaigo.{metric.key}/1" or metric.unit != "minor_currency" or metric.measurement != "flow":
                raise ConnectorError("METRIC_DEFINITION_MISMATCH")
            identity = (metric.key, metric.currency, metric.period_start, metric.period_end, metric.timezone, metric.tax_basis)
            if identity in identities:
                raise ConnectorError("DUPLICATE_METRIC")
            identities.add(identity)
            metrics.append({**metric.model_dump(), "label": QIDAIGO_METRICS[metric.key]})
        if source.complete and {metric.key for metric in source.metrics} != set(QIDAIGO_METRICS):
            raise ConnectorError("METRIC_COVERAGE_INCOMPLETE")
        projection = {"product": "qidaigo", "label": PRODUCTS["qidaigo"], "status": "connected", "environment": config.environment,
                      "scope": PORTFOLIO_SCOPE, "source_at": source_at.isoformat(), "synced_at": now.isoformat(),
                      "expires_at": min(now + timedelta(seconds=config.cache_ttl_seconds), source_at + timedelta(seconds=config.source_max_age_seconds), datetime.fromtimestamp(claims["exp"], timezone.utc)).isoformat(),
                      "complete": source.complete, "synthetic": source.synthetic, "metrics": metrics,
                      "health": {"status": source.health if source.complete else "unknown", "reason": "來源簽章驗證通過；健康由來源提供"},
                      "tasks": {"open": source.tasks_open, "overdue": source.tasks_overdue},
                      "costs": {"status": "not_configured", "items": [], "reason": "SaaS 帳單與分攤政策尚未核定"},
                      "deep_link": config.qidaigo_deep_link or None, "reason": None}
        return projection, binding
    except httpx.TimeoutException as exc:
        raise ConnectorError("SOURCE_TIMEOUT") from exc
    except httpx.HTTPError as exc:
        raise ConnectorError("SOURCE_NETWORK_ERROR") from exc
    except (ValidationError, ValueError, TypeError) as exc:
        raise ConnectorError("SOURCE_SCHEMA_INVALID") from exc


def disconnected(product, config, state="disconnected", reason="來源尚未連線", row=None):
    return {"product": product, "label": PRODUCTS[product], "status": state, "environment": config.environment,
            "scope": PORTFOLIO_SCOPE, "source_at": aware(row.get("source_at")).isoformat() if row and row.get("source_at") else None,
            "synced_at": aware(row.get("synced_at")).isoformat() if row and row.get("synced_at") else None,
            "expires_at": aware(row.get("expires_at")).isoformat() if row and row.get("expires_at") else None,
            "complete": False, "synthetic": False, "metrics": [], "health": {"status": "unknown", "reason": reason},
            "tasks": {"open": None, "overdue": None}, "costs": {"status": "not_configured", "items": [], "reason": "未提供核定帳單"},
            "deep_link": None, "reason": reason}


def connector_row(ctx, product, config):
    return one(ctx.conn, connectors, ctx.tenant_id, connectors.c.product == product, connectors.c.environment == config.environment)


def read_qidaigo(ctx, config, now=None):
    now = now or m.now()
    row = connector_row(ctx, "qidaigo", config)
    if row and row["status"] == "revoked":
        return disconnected("qidaigo", config, "revoked", "來源授權已停用，快取已清除", row)
    try:
        _, binding = credential_binding(config, ctx.tenant_id, now)
    except ConnectorError as exc:
        return disconnected("qidaigo", config, exc.state, exc.code, row)
    if not row or not row["projection"]:
        return disconnected("qidaigo", config, row["status"] if row else "disconnected", row.get("error_code") if row else "等待 owner 驗證並刷新", row)
    if row["grant_binding"] != binding:
        return disconnected("qidaigo", config, "revoked", "來源憑證已更換，舊快取禁止使用", row)
    if aware(row["expires_at"]) <= now:
        return disconnected("qidaigo", config, "stale", "快取已逾 TTL，請重新驗證來源", row)
    return row["projection"]


def _sum(ctx, table, column, *conditions):
    return int(ctx.conn.execute(select(func.coalesce(func.sum(column), 0)).where(table.c.tenant_id == ctx.tenant_id, *conditions)).scalar_one())


def _count(ctx, table, *conditions):
    return int(ctx.conn.execute(select(func.count()).select_from(table).where(table.c.tenant_id == ctx.tenant_id, *conditions)).scalar_one())


def local_summary(ctx, config, now=None):
    now = now or m.now()
    row = connector_row(ctx, "kuanguard", config)
    if row and row["status"] == "revoked":
        return disconnected("kuanguard", config, "revoked", "本機公司總覽 projection 已停用", row)
    local = now.astimezone(ZoneInfo("Asia/Taipei"))
    period = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    metrics = []
    def metric(key, label, value, unit="minor_currency", currency="TWD", reason=None, balance=False):
        metrics.append({"key": key, "label": label, "value": value, "unit": unit, "currency": currency if unit == "minor_currency" else None,
                        "tax_basis": "unknown" if unit == "minor_currency" else "not_applicable", "definition_version": f"kuanguard.{key}/1",
                        "period_start": (now if balance else period).isoformat(), "period_end": now.isoformat(), "timezone": "Asia/Taipei",
                        "measurement": "balance" if balance else "flow", "verified": value is not None, "reason": reason})
    contract_rows = ctx.conn.execute(select(m.quotes.c.currency, func.sum(m.contracts.c.amount_minor)).select_from(m.contracts.join(m.quotes,
            (m.contracts.c.quote_id == m.quotes.c.id) & (m.contracts.c.tenant_id == m.quotes.c.tenant_id))).where(
            m.contracts.c.tenant_id == ctx.tenant_id, m.contracts.c.created_at >= period, m.contracts.c.status == "active").group_by(m.quotes.c.currency)).all()
    if contract_rows:
        for currency, amount in contract_rows:
            metric("contracted_amount", "本期成立合約額（非收入認列）", int(amount or 0), currency=currency)
    else:
        metric("contracted_amount", "本期成立合約額（非收入認列）", 0)
    metric("cash_received", "資安服務實收", None, reason="尚無服務合約收款關聯；點數購買付款獨立列示")
    metric("refunds", "資安服務退款", None, reason="服務合約退款帳未啟用；點數退款獨立列示")
    metric("accounts_receivable", "資安服務應收", None, reason="缺服務收款及帳期基準，無法推算應收")
    paid = ctx.conn.execute(select(m.payments.c.currency, func.sum(m.payments.c.amount_minor)).where(m.payments.c.tenant_id == ctx.tenant_id,
            m.payments.c.created_at >= period, m.payments.c.status == "paid").group_by(m.payments.c.currency)).all()
    if paid:
        for currency, amount in paid:
            metric("points_purchase_cash", "本期購點收款（不與耗用相加）", int(amount or 0), currency=currency)
    else:
        metric("points_purchase_cash", "本期購點收款（不與耗用相加）", 0)
    refunds = ctx.conn.execute(select(m.orders.c.currency, func.sum(m.refunds.c.amount_minor)).select_from(m.refunds.join(m.orders,
            (m.refunds.c.order_id == m.orders.c.id) & (m.refunds.c.tenant_id == m.orders.c.tenant_id))).where(m.refunds.c.tenant_id == ctx.tenant_id,
            m.refunds.c.created_at >= period, m.refunds.c.status.in_(["completed", "completed_sandbox"])).group_by(m.orders.c.currency)).all()
    if refunds:
        for currency, amount in refunds:
            metric("points_purchase_refunds", "本期點數購買退款", int(amount or 0), currency=currency)
    else:
        metric("points_purchase_refunds", "本期點數購買退款", 0)
    metric("points_purchased", "本期購買點數", _sum(ctx, m.point_lots, m.point_lots.c.quantity, m.point_lots.c.created_at >= period,
           m.point_lots.c.source.in_(["paid", "paid_sandbox"]), m.point_lots.c.order_id.is_not(None)), "points")
    metric("points_reserved", "目前預留點數", _sum(ctx, m.wallet_transactions, m.wallet_transactions.c.reserved_delta), "points", balance=True)
    metric("points_consumed", "本期耗用點數", _sum(ctx, m.wallet_transactions, m.wallet_transactions.c.consumed_delta, m.wallet_transactions.c.created_at >= period), "points")
    return {"product": "kuanguard", "label": PRODUCTS["kuanguard"], "status": "connected", "environment": config.environment,
            "scope": "current_authorized_tenant_summary", "source_at": now.isoformat(), "synced_at": now.isoformat(), "expires_at": now.isoformat(),
            "complete": False, "synthetic": app_settings().app_env in {"development", "test"}, "metrics": metrics,
            "health": {"status": "unknown", "reason": "本機資料庫彙總成功；未取代正式部署、郵件、付款與掃描健康驗證"},
            "tasks": {"open": _count(ctx, m.tasks, m.tasks.c.status == "open"), "overdue": _count(ctx, m.tasks, m.tasks.c.status == "open", m.tasks.c.due_at < now)},
            "operations": {"projects": _count(ctx, m.projects), "batches": _count(ctx, m.batches), "campaigns": _count(ctx, m.campaigns), "enrollments": _count(ctx, m.enrollments)},
            "costs": {"status": "not_configured", "items": [], "reason": "尚未接入核定 SaaS 帳單及預算，不以零成本表示"},
            "deep_link": "/overview", "reason": "僅目前已授權租戶的去識別彙總；非正式財報"}


def persist_refresh(ctx, product, config, *, transport=None, now=None):
    now = now or m.now()
    row = connector_row(ctx, product, config)
    if row and row["status"] == "revoked":
        if product == "kuanguard":
            change(ctx.conn, connectors, ctx.tenant_id, row["id"], status="connected", generation=row["generation"] + 1)
            ctx.audit("portfolio.connector.refresh", product, "owner explicitly reenabled local summary")
            return local_summary(ctx, config, now)
        try:
            _, new_binding = credential_binding(config, ctx.tenant_id, now)
        except ConnectorError:
            new_binding = None
        if not new_binding or new_binding == row["grant_binding"]:
            return disconnected(product, config, "revoked", "需配置新的核定唯讀 grant 才可重新連線", row)
    if product == "kuanguard":
        return local_summary(ctx, config, now)
    try:
        projection, binding = fetch_qidaigo(config, ctx.tenant_id, now=now, transport=transport)
        values = {"status": "connected", "projection": projection, "grant_binding": binding,
                  "source_at": datetime.fromisoformat(projection["source_at"]), "synced_at": now,
                  "expires_at": datetime.fromisoformat(projection["expires_at"]), "error_code": None}
    except ConnectorError as exc:
        projection = disconnected(product, config, exc.state, exc.code)
        values = {"status": exc.state, "projection": None, "grant_binding": row.get("grant_binding") if row else None, "synced_at": now, "expires_at": None,
                  "source_at": None, "error_code": exc.code}
    if row:
        change(ctx.conn, connectors, ctx.tenant_id, row["id"], generation=row["generation"] + 1, **values)
    else:
        add(ctx.conn, connectors, ctx.tenant_id, product=product, environment=config.environment, generation=1, **values)
    ctx.audit("portfolio.connector.refresh", product, values["status"])
    return projection


def disable_connector(ctx, product, config):
    row = connector_row(ctx, product, config)
    binding = row.get("grant_binding") if row else None
    if not binding and product == "qidaigo":
        try:
            _, binding = credential_binding(config, ctx.tenant_id)
        except ConnectorError:
            pass
    values = {"status": "revoked", "projection": None, "grant_binding": binding, "source_at": None, "synced_at": None, "expires_at": None, "error_code": "OWNER_REVOKED"}
    if row:
        change(ctx.conn, connectors, ctx.tenant_id, row["id"], generation=row["generation"] + 1, **values)
    else:
        add(ctx.conn, connectors, ctx.tenant_id, product=product, environment=config.environment, generation=1, **values)
    ctx.audit("portfolio.connector.disable", product, "projection cleared; idempotency stores no financial data")
    return disconnected(product, config, "revoked", "來源授權已停用，快取已清除")


def portfolio_overview(ctx, config=None):
    config = config or portfolio_settings()
    ctx.require("portfolio_owner")
    now = m.now()
    return {"items": [local_summary(ctx, config, now), read_qidaigo(ctx, config, now)], "environment": config.environment,
            "combined_financial_total": None, "notice": "不同產品與指標不自動相加。GMV、合約、實收、購點與耗用各自列示，屬營運指標。",
            "updated_at": now.isoformat()}


def prune_expired_projections(conn, tenant_id, now=None):
    """Tenant-bound maintenance hook. Never processes arbitrary queue tenant data."""
    now = now or m.now()
    result = conn.execute(connectors.update().where(connectors.c.tenant_id == tenant_id, connectors.c.expires_at <= now,
                          connectors.c.projection.is_not(None)).values(projection=None, status="stale", error_code="CACHE_EXPIRED"))
    return result.rowcount
