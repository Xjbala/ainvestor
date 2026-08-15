# -*- coding: utf-8 -*-
"""
估值 API 路由

提供 DCF、剩余收益、相对估值、WACC、综合三角验证接口。
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import consume_quota
from ..persistence.db import get_db_session
from ..persistence.orm_models import QuotaResource
from ..valuation import DCFValuationService, ResidualIncomeService
from ..valuation.relative import RelativeValuationService
from ..valuation.sotp import SOTPValuationService
from ..valuation.triangulate import TriangulationService
from ..valuation.wacc import WACCService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/valuation", tags=["估值分析"])

# 估值端点统一挂 expert_valuation 配额守卫。
# 一次调用扣 1 次；一个股票可反复调参数，每次都计入配额。
_EXPERT_QUOTA_DEP = Depends(consume_quota(QuotaResource.EXPERT_VALUATION))


class ValuationResponse(BaseModel):
    """估值响应（宽松，兼容多方法）"""

    company: Optional[dict] = None
    method: Optional[str] = None
    parameters: Optional[dict] = None
    inputs: Optional[dict] = None
    valuation: Optional[dict] = None
    current_price: Optional[float] = None
    upside_downside: Optional[float] = None
    investment_rating: Optional[str] = None
    margin_of_safety: Optional[dict] = None
    wacc_breakdown: Optional[dict] = None
    gates: Optional[list] = None
    error: Optional[str] = None

    class Config:
        extra = "allow"


class ComparisonResponse(BaseModel):
    """估值对比响应"""

    stock_code: str
    stock_name: Optional[str] = None
    dcf_value: Optional[float] = None
    ri_value: Optional[float] = None
    relative_value: Optional[float] = None
    average_value: Optional[float] = None
    blended_price: Optional[float] = None
    current_price: Optional[float] = None
    divergence_pct: Optional[float] = None
    confidence: Optional[str] = None
    recommendation: Optional[str] = None
    headline: Optional[str] = None


@router.get("/dcf/{stock_code}", response_model=ValuationResponse, dependencies=[_EXPERT_QUOTA_DEP])
async def dcf_valuation(
    stock_code: str,
    high_growth_years: int = Query(5, ge=1, le=10),
    high_growth_rate: float = Query(None, ge=0, le=1),
    growth_rate: float = Query(None, ge=0, le=1),
    terminal_growth_rate: float = Query(0.03, ge=0, le=0.1),
    discount_rate: float = Query(None, ge=0.01, le=0.3),
    tax_rate: float = Query(None, ge=0, le=0.5),
    projection_years: int = Query(None, ge=1, le=10),
    session: AsyncSession = Depends(get_db_session),
):
    """
    DCF 估值（自动 WACC + 双终值 + 敏感性）。
    未传 discount_rate 时自动 CAPM/WACC。
    """
    service = DCFValuationService(session)
    params: Dict[str, Any] = {
        "terminal_growth_rate": terminal_growth_rate,
    }
    gr = growth_rate if growth_rate is not None else high_growth_rate
    if gr is not None:
        params["growth_rate"] = gr
    if discount_rate is not None:
        params["discount_rate"] = discount_rate
    if tax_rate is not None:
        params["tax_rate"] = tax_rate
    years = projection_years if projection_years is not None else high_growth_years
    params["projection_years"] = years

    result = await service.valuate(stock_code, valuation_date=None, params=params)
    return result


@router.get("/residual-income/{stock_code}", response_model=ValuationResponse, dependencies=[_EXPERT_QUOTA_DEP])
async def residual_income_valuation(
    stock_code: str,
    cost_of_equity: float = Query(None, ge=0.01, le=0.3),
    forecast_years: int = Query(5, ge=1, le=10),
    growth_rate: float = Query(0.15, ge=0, le=1),
    terminal_growth_rate: float = Query(0.03, ge=0, le=0.1),
    payout_ratio: float = Query(0.30, ge=0, le=1),
    session: AsyncSession = Depends(get_db_session),
):
    """剩余收益估值。未传 cost_of_equity 时尝试使用 CAPM Ke。"""
    service = ResidualIncomeService(session)
    params: Dict[str, Any] = {
        "growth_rate": growth_rate,
        "terminal_growth_rate": terminal_growth_rate,
        "projection_years": forecast_years,
        "payout_ratio": payout_ratio,
    }
    if cost_of_equity is not None:
        params["cost_of_equity"] = cost_of_equity
    else:
        try:
            wacc = await WACCService(session).calculate(stock_code)
            if "ke" in wacc:
                params["cost_of_equity"] = wacc["ke"]
        except Exception:
            params["cost_of_equity"] = 0.09

    result = await service.valuate(stock_code, valuation_date=None, params=params)
    return result


@router.get("/relative/{stock_code}", dependencies=[_EXPERT_QUOTA_DEP])
async def relative_valuation(
    stock_code: str,
    session: AsyncSession = Depends(get_db_session),
):
    """相对估值（同业中位数倍数）。"""
    service = RelativeValuationService(session)
    return await service.valuate(stock_code)


@router.get("/wacc/{stock_code}", dependencies=[_EXPERT_QUOTA_DEP])
async def wacc_breakdown(
    stock_code: str,
    session: AsyncSession = Depends(get_db_session),
):
    """WACC / CAPM 拆解。"""
    service = WACCService(session)
    return await service.calculate(stock_code)


@router.get("/triangulate/{stock_code}", dependencies=[_EXPERT_QUOTA_DEP])
async def triangulate_valuation(
    stock_code: str,
    session: AsyncSession = Depends(get_db_session),
):
    """多方法三角验证综合估值（DCF + RI + Relative + SOTP-if-any）。"""
    service = TriangulationService(session)
    return await service.valuate(stock_code)


@router.get("/sotp/{stock_code}", dependencies=[_EXPERT_QUOTA_DEP])
async def sotp_valuation(
    stock_code: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    分部加总估值。无内置分部数据时返回 applicable=false。
    需要业务方通过服务层传入 segments（API 当前只做存在性探测）。
    """
    service = SOTPValuationService(session)
    return await service.valuate(stock_code)


@router.get("/compare/{stock_code}", response_model=ComparisonResponse, dependencies=[_EXPERT_QUOTA_DEP])
async def compare_valuations(
    stock_code: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    估值对比（兼容旧接口，内部走三角验证）。
    """
    service = TriangulationService(session)
    tri = await service.valuate(stock_code)

    method_map = {m["method"]: m for m in tri.get("methods") or []}
    dcf_value = (method_map.get("DCF") or {}).get("implied_price")
    ri_value = (method_map.get("RI") or {}).get("implied_price")
    rel_value = (method_map.get("RELATIVE") or {}).get("implied_price")

    values = [v for v in [dcf_value, ri_value, rel_value] if v and v > 0]
    average_value = sum(values) / len(values) if values else None
    blended = tri.get("blended_price") or average_value
    current_price = tri.get("current_price")

    recommendation = tri.get("margin_of_safety", {}).get("recommendation") if tri.get("margin_of_safety") else None
    if not recommendation and blended and current_price:
        margin = (blended - current_price) / blended * 100
        if margin >= 30:
            recommendation = "明显低估，具有较高安全边际，可考虑买入"
        elif margin >= 10:
            recommendation = "估值合理偏低，可逢低布局"
        elif margin >= 0:
            recommendation = "估值合理，可持有观望"
        elif margin >= -20:
            recommendation = "略微高估，不建议追高"
        else:
            recommendation = "明显高估，建议回避"
    if not recommendation:
        recommendation = "数据不足，无法给出建议"

    company = tri.get("company") or {}

    return ComparisonResponse(
        stock_code=stock_code,
        stock_name=company.get("stock_name"),
        dcf_value=dcf_value,
        ri_value=ri_value,
        relative_value=rel_value,
        average_value=round(average_value, 2) if average_value else None,
        blended_price=round(blended, 2) if blended else None,
        current_price=current_price,
        divergence_pct=tri.get("divergence_pct"),
        confidence=tri.get("confidence"),
        recommendation=recommendation,
        headline=tri.get("headline"),
    )
