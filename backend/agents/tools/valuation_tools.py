# -*- coding: utf-8 -*-
"""
估值分析师工具函数

封装 DCF、剩余收益、相对估值、WACC、综合三角验证，供 AgentScope ReActAgent 调用。
"""

import json
import logging
from typing import Optional

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from backend.persistence.db import async_session_factory
from backend.agents.tools.stock_code import normalize_stock_code

logger = logging.getLogger(__name__)


def _ok(payload: dict) -> ToolResponse:
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    return ToolResponse(content=[TextBlock(type="text", text=text)])


def _err(msg: str) -> ToolResponse:
    return _ok({"error": msg})


async def dcf_valuation_analysis(
    stock_code: str,
    growth_rate: float = 0.15,
    terminal_growth_rate: float = 0.03,
    discount_rate: float = None,
    projection_years: int = 5,
) -> ToolResponse:
    """
    Perform DCF (Discounted Cash Flow) valuation for a company.

    Uses two-stage growth, auto WACC (CAPM) when discount_rate is omitted,
    dual terminal value (Gordon + exit multiple midpoint), scenario analysis,
    sensitivity grid, and quality gates.

    Args:
        stock_code: Stock ticker (e.g. "600519")
        growth_rate: High-growth FCF growth rate (default 0.15)
        terminal_growth_rate: Perpetual growth (default 0.03)
        discount_rate: Optional WACC override; omit to auto-calculate CAPM WACC
        projection_years: Explicit forecast years (default 5)

    Returns:
        JSON with intrinsic value, wacc_breakdown, terminal_methods, gates, sensitivity.
    """
    from backend.valuation.dcf import DCFValuationService

    try:
        stock_code = normalize_stock_code(stock_code)
        async with async_session_factory() as session:
            service = DCFValuationService(session)
            params = {
                "growth_rate": growth_rate,
                "terminal_growth_rate": terminal_growth_rate,
                "projection_years": projection_years,
            }
            if discount_rate is not None:
                params["discount_rate"] = discount_rate
            result = await service.valuate(stock_code=stock_code, valuation_date=None, params=params)
            return _ok(result)
    except Exception as e:
        logger.error(f"dcf_valuation_analysis failed for {stock_code}: {e}")
        return _err(f"DCF估值分析失败: {str(e)}")


async def residual_income_valuation_analysis(
    stock_code: str,
    cost_of_equity: float = None,
    growth_rate: float = 0.15,
    terminal_growth_rate: float = 0.03,
    projection_years: int = 5,
    payout_ratio: float = 0.30,
) -> ToolResponse:
    """
    Perform Residual Income (RI) valuation.

    RI = EPS - (Ke × beginning BPS)
    Intrinsic = BPS + PV(forecast RI) + PV(terminal)

    Best for high-ROE firms and banks when DCF FCF is unreliable.
    If cost_of_equity omitted, uses CAPM Ke from WACC service.

    Args:
        stock_code: Stock ticker
        cost_of_equity: Optional Ke override
        growth_rate: EPS growth in forecast window
        terminal_growth_rate: Perpetual growth of RI
        projection_years: Forecast years
        payout_ratio: Dividend payout ratio
    """
    from backend.valuation.residual_income import ResidualIncomeService
    from backend.valuation.wacc import WACCService

    try:
        stock_code = normalize_stock_code(stock_code)
        async with async_session_factory() as session:
            params = {
                "growth_rate": growth_rate,
                "terminal_growth_rate": terminal_growth_rate,
                "projection_years": projection_years,
                "payout_ratio": payout_ratio,
            }
            if cost_of_equity is not None:
                params["cost_of_equity"] = cost_of_equity
            else:
                wacc = await WACCService(session).calculate(stock_code)
                params["cost_of_equity"] = wacc.get("ke", 0.09)
            service = ResidualIncomeService(session)
            result = await service.valuate(stock_code=stock_code, valuation_date=None, params=params)
            return _ok(result)
    except Exception as e:
        logger.error(f"residual_income_valuation_analysis failed for {stock_code}: {e}")
        return _err(f"剩余收益估值分析失败: {str(e)}")


async def relative_valuation_analysis(
    stock_code: str,
) -> ToolResponse:
    """
    Peer multiple relative valuation using same-industry A-share peers.

    Uses median PE/PB/PS with quality adjustment (e.g. ROE vs peers).
    Banks/insurance prefer PB. Requires at least 3 peers.

    Args:
        stock_code: Stock ticker
    """
    from backend.valuation.relative import RelativeValuationService

    try:
        stock_code = normalize_stock_code(stock_code)
        async with async_session_factory() as session:
            service = RelativeValuationService(session)
            result = await service.valuate(stock_code)
            return _ok(result)
    except Exception as e:
        logger.error(f"relative_valuation_analysis failed for {stock_code}: {e}")
        return _err(f"相对估值分析失败: {str(e)}")


async def get_wacc_breakdown(
    stock_code: str,
) -> ToolResponse:
    """
    Calculate WACC via CAPM: Ke = rf + beta * ERP + size premium;
    WACC = E/V * Ke + D/V * Kd * (1-t).

    Use before adjusting DCF discount_rate. Returns full component breakdown
    and sector sanity band.

    Args:
        stock_code: Stock ticker
    """
    from backend.valuation.wacc import WACCService

    try:
        stock_code = normalize_stock_code(stock_code)
        async with async_session_factory() as session:
            result = await WACCService(session).calculate(stock_code)
            return _ok(result)
    except Exception as e:
        logger.error(f"get_wacc_breakdown failed for {stock_code}: {e}")
        return _err(f"WACC计算失败: {str(e)}")


async def comprehensive_valuation_analysis(
    stock_code: str,
) -> ToolResponse:
    """
    PRIMARY valuation tool: triangulate DCF + Residual Income + Relative (+ SOTP if data).

    Prefer this over calling DCF/RI/Relative separately. Returns blended fair value,
    method weights, divergence, confidence, headline, risks, WACC, and sensitivity.

    Methodology selection is industry-aware (e.g. banks down-weight DCF, use PB).

    Args:
        stock_code: Stock ticker (e.g. "600519", "000858")
    """
    from backend.valuation.triangulate import TriangulationService

    try:
        stock_code = normalize_stock_code(stock_code)
        async with async_session_factory() as session:
            result = await TriangulationService(session).valuate(stock_code)
            return _ok(result)
    except Exception as e:
        logger.error(f"comprehensive_valuation_analysis failed for {stock_code}: {e}")
        return _err(f"综合估值分析失败: {str(e)}")


async def sotp_valuation_analysis(
    stock_code: str,
) -> ToolResponse:
    """
    Sum-of-the-parts valuation for multi-segment companies.

    Without segment financials this returns applicable=false. When segments exist,
    values each at peer multiples, subtracts corporate costs and net debt.

    Args:
        stock_code: Stock ticker
    """
    from backend.valuation.sotp import SOTPValuationService

    try:
        stock_code = normalize_stock_code(stock_code)
        async with async_session_factory() as session:
            result = await SOTPValuationService(session).valuate(stock_code)
            return _ok(result)
    except Exception as e:
        logger.error(f"sotp_valuation_analysis failed for {stock_code}: {e}")
        return _err(f"SOTP估值分析失败: {str(e)}")
