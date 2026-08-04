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
from .financial_validation import (
    CORE_SUBJECTS,
    ValidationStatus,
    validate_period,
    summarize_periods,
    is_year_complete_for_resume,
    required_core_codes,
    evaluate_cell_completeness,
    build_coverage_matrix,
)
from .coverage_service import (
    scan_coverage,
    scan_and_save,
    get_latest_snapshot,
    refresh_coverage_after_repair,
)

__all__ = [
    "SolvencyAnalysisService",
    "ProfitabilityAnalysisService",
    "GrowthAnalysisService",
    "OperatingAnalysisService",
    "CORE_SUBJECTS",
    "ValidationStatus",
    "validate_period",
    "summarize_periods",
    "is_year_complete_for_resume",
    "required_core_codes",
    "evaluate_cell_completeness",
    "build_coverage_matrix",
    "scan_coverage",
    "scan_and_save",
    "get_latest_snapshot",
    "refresh_coverage_after_repair",
]
