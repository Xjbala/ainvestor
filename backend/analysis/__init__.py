# -*- coding: utf-8 -*-
"""
财务分析模块初始化

提供四维财务分析能力：偿债能力、盈利能力、发展能力、营运能力。
移植自 leofun 项目。
"""

from .solvency import SolvencyAnalysisService
from .profitability import ProfitabilityAnalysisService
from .growth import GrowthAnalysisService
from .operating import OperatingAnalysisService

__all__ = [
    "SolvencyAnalysisService",
    "ProfitabilityAnalysisService",
    "GrowthAnalysisService",
    "OperatingAnalysisService",
]
