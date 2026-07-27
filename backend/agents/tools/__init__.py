# -*- coding: utf-8 -*-
"""
Agent 工具模块

提供分析师 Agent 使用的工具函数，封装已有的分析和估值服务。
"""

from .fundamentals_tools import (
    analyze_profitability,
    analyze_growth,
    analyze_solvency,
    analyze_operating,
)
from .valuation_tools import (
    dcf_valuation_analysis,
    residual_income_valuation_analysis,
    relative_valuation_analysis,
    get_wacc_breakdown,
    comprehensive_valuation_analysis,
    sotp_valuation_analysis,
)
from .qualitative_tools import (
    get_qualitative_insights,
    get_industry_competition,
    get_news_sentiment,
)

__all__ = [
    # 定量分析工具
    "analyze_profitability",
    "analyze_growth",
    "analyze_solvency",
    "analyze_operating",
    "dcf_valuation_analysis",
    "residual_income_valuation_analysis",
    "relative_valuation_analysis",
    "get_wacc_breakdown",
    "comprehensive_valuation_analysis",
    "sotp_valuation_analysis",
    # 定性分析工具
    "get_qualitative_insights",
    "get_industry_competition",
    "get_news_sentiment",
]
