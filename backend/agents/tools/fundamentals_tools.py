# -*- coding: utf-8 -*-
"""
基本面分析师工具函数

封装四维财务分析服务，供 AgentScope ReActAgent 工具调用。
每个工具函数内部自行管理数据库 session 生命周期。
"""

import json
import logging
from typing import Any, Dict

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

from backend.persistence.db import async_session_factory

logger = logging.getLogger(__name__)


async def analyze_profitability(
    stock_code: str,
    years: int = 5,
) -> ToolResponse:
    """
    Analyze a company's profitability over multiple years.

    Calculates key profitability indicators including:
    - Gross Margin (毛利率)
    - Operating Margin (营业利润率)
    - ROA (Return on Assets, 总资产报酬率)
    - ROE (Return on Equity, 净资产收益率)

    Also provides trend analysis and risk assessment conclusions.

    Args:
        stock_code: Stock ticker code (e.g., "600519", "000858")
        years: Number of years to analyze (default: 5)

    Returns:
        ToolResponse containing profitability analysis results with indicators,
        trend analysis, and investment conclusions.
    """
    from backend.analysis.profitability import ProfitabilityAnalysisService

    try:
        async with async_session_factory() as session:
            service = ProfitabilityAnalysisService(session)
            result = await service.analyze(stock_code=stock_code, years=years)
            text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
            return ToolResponse(content=[TextBlock(type="text", text=text)])
    except Exception as e:
        logger.error(f"analyze_profitability failed for {stock_code}: {e}")
        error_text = json.dumps({"error": f"盈利能力分析失败: {str(e)}"}, ensure_ascii=False)
        return ToolResponse(content=[TextBlock(type="text", text=error_text)])


async def analyze_growth(
    stock_code: str,
    years: int = 5,
) -> ToolResponse:
    """
    Analyze a company's growth capability over multiple years.

    Calculates key growth indicators including:
    - Revenue Growth Rate (营业收入增长率)
    - Net Profit Growth Rate (净利润增长率)
    - Total Assets Growth Rate (总资产增长率)
    - Net Assets Growth Rate (净资产增长率)

    Also provides trend analysis and growth stability assessment.

    Args:
        stock_code: Stock ticker code (e.g., "600519", "000858")
        years: Number of years to analyze (default: 5)

    Returns:
        ToolResponse containing growth analysis results with indicators,
        trend analysis, and investment conclusions.
    """
    from backend.analysis.growth import GrowthAnalysisService

    try:
        async with async_session_factory() as session:
            service = GrowthAnalysisService(session)
            result = await service.analyze(stock_code=stock_code, years=years)
            text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
            return ToolResponse(content=[TextBlock(type="text", text=text)])
    except Exception as e:
        logger.error(f"analyze_growth failed for {stock_code}: {e}")
        error_text = json.dumps({"error": f"发展能力分析失败: {str(e)}"}, ensure_ascii=False)
        return ToolResponse(content=[TextBlock(type="text", text=error_text)])


async def analyze_solvency(
    stock_code: str,
    years: int = 5,
) -> ToolResponse:
    """
    Analyze a company's solvency (debt-paying ability) over multiple years.

    Calculates key solvency indicators including:
    - Debt-to-Asset Ratio (资产负债率) - measures long-term solvency
    - Equity Ratio (产权比率) - debt to equity proportion
    - Current Ratio (流动比率) - measures short-term solvency
    - Quick Ratio (速动比率) - excludes inventory from current assets

    Also provides trend analysis and risk assessment conclusions.

    Args:
        stock_code: Stock ticker code (e.g., "600519", "000858")
        years: Number of years to analyze (default: 5)

    Returns:
        ToolResponse containing solvency analysis results with indicators,
        trend analysis, and investment conclusions.
    """
    from backend.analysis.solvency import SolvencyAnalysisService

    try:
        async with async_session_factory() as session:
            service = SolvencyAnalysisService(session)
            result = await service.analyze(stock_code=stock_code, years=years)
            text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
            return ToolResponse(content=[TextBlock(type="text", text=text)])
    except Exception as e:
        logger.error(f"analyze_solvency failed for {stock_code}: {e}")
        error_text = json.dumps({"error": f"偿债能力分析失败: {str(e)}"}, ensure_ascii=False)
        return ToolResponse(content=[TextBlock(type="text", text=error_text)])


async def analyze_operating(
    stock_code: str,
    years: int = 5,
) -> ToolResponse:
    """
    Analyze a company's operating efficiency over multiple years.

    Calculates key operating indicators including:
    - Total Asset Turnover (总资产周转率) - overall asset utilization
    - Current Asset Turnover (流动资产周转率) - working capital efficiency
    - Receivables Turnover (应收账款周转率) - collection efficiency
    - Inventory Turnover (存货周转率) - inventory management efficiency

    Also provides trend analysis and operational efficiency conclusions.

    Args:
        stock_code: Stock ticker code (e.g., "600519", "000858")
        years: Number of years to analyze (default: 5)

    Returns:
        ToolResponse containing operating analysis results with indicators,
        trend analysis, and investment conclusions.
    """
    from backend.analysis.operating import OperatingAnalysisService

    try:
        async with async_session_factory() as session:
            service = OperatingAnalysisService(session)
            result = await service.analyze(stock_code=stock_code, years=years)
            text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
            return ToolResponse(content=[TextBlock(type="text", text=text)])
    except Exception as e:
        logger.error(f"analyze_operating failed for {stock_code}: {e}")
        error_text = json.dumps({"error": f"营运能力分析失败: {str(e)}"}, ensure_ascii=False)
        return ToolResponse(content=[TextBlock(type="text", text=error_text)])
