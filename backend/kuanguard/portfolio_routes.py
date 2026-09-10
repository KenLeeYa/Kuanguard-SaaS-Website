from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from .portfolio import (disable_connector, persist_refresh, portfolio_overview, portfolio_settings,
                        read_qidaigo, local_summary)
from .security import Context, context, fail, idempotent

router = APIRouter(prefix="/internal/portfolio", tags=["portfolio"])
Product = Literal["kuanguard", "qidaigo"]


class NoOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.get("")
@router.get("/products")
@router.get("/finance")
@router.get("/tasks")
@router.get("/operations")
@router.get("/costs")
@router.get("/integrations")
@router.get("/connectors")
def overview(request: Request, ctx: Context = Depends(context)):
    if request.query_params:
        fail(422, "PORTFOLIO_QUERY_FORBIDDEN", "總覽範圍由已驗證 owner 與租戶授權決定。")
    return portfolio_overview(ctx)


@router.get("/connectors/{product}")
def connector(product: Product, request: Request, ctx: Context = Depends(context)):
    ctx.require("portfolio_owner")
    if request.query_params:
        fail(422, "PORTFOLIO_QUERY_FORBIDDEN", "Connector 範圍不能由請求指定。")
    config = portfolio_settings()
    return local_summary(ctx, config) if product == "kuanguard" else read_qidaigo(ctx, config)


@router.post("/connectors/{product}/refresh")
def refresh(product: Product, request: Request, payload: NoOverrides | None = None, ctx: Context = Depends(context)):
    ctx.require("portfolio_owner")
    if request.query_params:
        fail(422, "PORTFOLIO_QUERY_FORBIDDEN", "Connector 來源、環境與範圍由核定設定綁定。")
    config = portfolio_settings()
    def perform():
        result = persist_refresh(ctx, product, config)
        # Store only an operation receipt. Replays read current TTL/grant status.
        return {"product": product, "status": result["status"]}
    idempotent(ctx, request, f"portfolio.refresh.{product}", {"product": product, "environment": config.environment}, perform)
    return local_summary(ctx, config) if product == "kuanguard" else read_qidaigo(ctx, config)


@router.post("/connectors/{product}/disable")
def disable(product: Product, request: Request, payload: NoOverrides | None = None, ctx: Context = Depends(context)):
    ctx.require("portfolio_owner")
    if request.query_params:
        fail(422, "PORTFOLIO_QUERY_FORBIDDEN", "Connector 範圍不能由請求指定。")
    config = portfolio_settings()
    idempotent(ctx, request, f"portfolio.disable.{product}", {"product": product, "environment": config.environment},
               lambda: {"product": product, "status": disable_connector(ctx, product, config)["status"]})
    return local_summary(ctx, config) if product == "kuanguard" else read_qidaigo(ctx, config)
