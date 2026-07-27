# -*- coding: utf-8 -*-
"""
财务分析 API 路由

提供四维财务分析接口：偿债能力、盈利能力、发展能力、营运能力。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_current_user
from ..persistence.db import get_db_session
from ..persistence.orm_models import User
from ..analysis import (
    SolvencyAnalysisService,
    ProfitabilityAnalysisService,
    GrowthAnalysisService,
    OperatingAnalysisService,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analysis", tags=["财务分析"])


# ============================================================
# 请求/响应模型
# ============================================================

class AnalysisRequest(BaseModel):
    """分析请求"""
    stock_code: str = Field(..., description="股票代码")
    years: int = Field(default=5, ge=1, le=10, description="分析年数")


class AnalysisResponse(BaseModel):
    """分析响应"""
    company: Optional[dict] = None
    analysis_period: Optional[dict] = None
    indicators: list = []
    trend_analysis: dict = {}
    conclusion: dict = {}
    error: Optional[str] = None


class SummaryResponse(BaseModel):
    """综合分析摘要"""
    stock_code: str
    stock_name: Optional[str] = None
    solvency_risk: str
    profitability_risk: str
    growth_risk: str
    operating_risk: str
    overall_risk: str
    summary: str


# ============================================================
# 分析路由
# ============================================================

@router.get("/solvency/{stock_code}", response_model=AnalysisResponse)
async def analyze_solvency(
    stock_code: str,
    years: int = Query(5, ge=1, le=10),
    session: AsyncSession = Depends(get_db_session),
):
    """
    偿债能力分析

    分析企业的短期和长期偿债能力，包括：
    - 流动比率
    - 速动比率
    - 资产负债率
    - 产权比率
    """
    service = SolvencyAnalysisService(session)
    result = await service.analyze(stock_code, years)
    return AnalysisResponse(**result)


@router.get("/profitability/{stock_code}", response_model=AnalysisResponse)
async def analyze_profitability(
    stock_code: str,
    years: int = Query(5, ge=1, le=10),
    session: AsyncSession = Depends(get_db_session),
):
    """
    盈利能力分析

    分析企业的盈利水平，包括：
    - 毛利率
    - 营业利润率
    - ROA（总资产报酬率）
    - ROE（净资产收益率）
    """
    service = ProfitabilityAnalysisService(session)
    result = await service.analyze(stock_code, years)
    return AnalysisResponse(**result)


@router.get("/growth/{stock_code}", response_model=AnalysisResponse)
async def analyze_growth(
    stock_code: str,
    years: int = Query(5, ge=1, le=10),
    session: AsyncSession = Depends(get_db_session),
):
    """
    发展能力分析

    分析企业的成长潜力，包括：
    - 营业收入增长率
    - 净利润增长率
    - 总资产增长率
    - 净资产增长率
    """
    service = GrowthAnalysisService(session)
    result = await service.analyze(stock_code, years)
    return AnalysisResponse(**result)


@router.get("/operating/{stock_code}", response_model=AnalysisResponse)
async def analyze_operating(
    stock_code: str,
    years: int = Query(5, ge=1, le=10),
    session: AsyncSession = Depends(get_db_session),
):
    """
    营运能力分析

    分析企业的运营效率，包括：
    - 总资产周转率
    - 流动资产周转率
    - 应收账款周转率
    - 存货周转率
    """
    service = OperatingAnalysisService(session)
    result = await service.analyze(stock_code, years)
    return AnalysisResponse(**result)


@router.get("/summary/{stock_code}", response_model=SummaryResponse)
async def get_analysis_summary(
    stock_code: str,
    years: int = Query(5, ge=1, le=10),
    session: AsyncSession = Depends(get_db_session),
):
    """
    综合财务分析摘要

    汇总四维财务分析结果，给出整体评估。
    """
    # 执行四维分析
    solvency_service = SolvencyAnalysisService(session)
    profitability_service = ProfitabilityAnalysisService(session)
    growth_service = GrowthAnalysisService(session)
    operating_service = OperatingAnalysisService(session)

    solvency = await solvency_service.analyze(stock_code, years)
    profitability = await profitability_service.analyze(stock_code, years)
    growth = await growth_service.analyze(stock_code, years)
    operating = await operating_service.analyze(stock_code, years)

    # 提取公司信息
    company = solvency.get("company") or profitability.get("company") or {}

    # 提取风险等级
    solvency_risk = solvency.get("conclusion", {}).get("risk_level", "unknown")
    profitability_risk = profitability.get("conclusion", {}).get("risk_level", "unknown")
    growth_risk = growth.get("conclusion", {}).get("risk_level", "unknown")
    operating_risk = operating.get("conclusion", {}).get("risk_level", "unknown")

    # 计算综合风险
    risk_scores = {"low": 1, "medium": 2, "high": 3, "unknown": 2}
    avg_risk = (
        risk_scores.get(solvency_risk, 2) +
        risk_scores.get(profitability_risk, 2) +
        risk_scores.get(growth_risk, 2) +
        risk_scores.get(operating_risk, 2)
    ) / 4

    if avg_risk <= 1.5:
        overall_risk = "low"
        overall_assessment = "财务状况优秀"
    elif avg_risk <= 2.0:
        overall_risk = "medium"
        overall_assessment = "财务状况良好"
    elif avg_risk <= 2.5:
        overall_risk = "medium"
        overall_assessment = "财务状况一般"
    else:
        overall_risk = "high"
        overall_assessment = "财务状况需关注"

    # 生成摘要
    summary_parts = []
    if solvency.get("conclusion", {}).get("summary"):
        summary_parts.append(solvency["conclusion"]["summary"])
    if profitability.get("conclusion", {}).get("summary"):
        summary_parts.append(profitability["conclusion"]["summary"])
    if growth.get("conclusion", {}).get("summary"):
        summary_parts.append(growth["conclusion"]["summary"])
    if operating.get("conclusion", {}).get("summary"):
        summary_parts.append(operating["conclusion"]["summary"])

    summary = f"综合评估：{overall_assessment}。" + " ".join(summary_parts[:2])

    return SummaryResponse(
        stock_code=stock_code,
        stock_name=company.get("stock_name"),
        solvency_risk=solvency_risk,
        profitability_risk=profitability_risk,
        growth_risk=growth_risk,
        operating_risk=operating_risk,
        overall_risk=overall_risk,
        summary=summary,
    )
