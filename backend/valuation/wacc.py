# -*- coding: utf-8 -*-
"""
WACC / CAPM 计算服务。

Ke = rf + β × ERP + size_premium
WACC = (E/V)×Ke + (D/V)×Kd×(1−t)
"""

from __future__ import annotations

import logging
import os
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..persistence.financial_models import Company, FinancialData, ReportType
from .industry_profiles import get_industry_profile

logger = logging.getLogger(__name__)


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class WACCService:
    """CAPM 驱动的 WACC 拆解。"""

    # 利息费用（非银行企业使用利润表明细科目 ISF005）
    INTEREST_CODES = ["ISF005"]  # 其中：利息费用
    # 有息债务科目
    SHORT_DEBT_CODES = ["BSL001", "BSL002", "BSL003"]
    LONG_DEBT_CODES = ["BSL102", "BSL103"]
    CASH_CODES = ["BSA001", "BSA002", "BSA003"]
    TAX_CODES = ["ISF020"]
    EBT_CODES = ["ISF019"]  # 利润总额（不含营业外支出，避免重复扣减）
    NET_INCOME_CODES = ["ISF021"]
    OPERATING_INCOME_CODES = ["ISF016"]

    def __init__(self, session: AsyncSession):
        self.session = session
        self.rf = _env_float("RISK_FREE_RATE", 0.025)
        self.erp = _env_float("EQUITY_RISK_PREMIUM", 0.065)
        self.default_kd = _env_float("DEFAULT_COST_OF_DEBT", 0.055)

    async def calculate(
        self,
        stock_code: str,
        *,
        beta_override: Optional[float] = None,
        tax_rate_override: Optional[float] = None,
    ) -> Dict[str, Any]:
        company = await self._get_company(stock_code)
        if not company:
            return {"error": f"公司不存在: {stock_code}", "wacc": 0.10}

        industry_name = company.industry.name if company.industry else None
        profile = get_industry_profile(industry_name)

        market_cap = self._to_float(company.market_cap)
        # market_cap 库内单位为万元；转元以与财务科目一致时需 *10000
        # 但 net_debt 来自财务报表 value_decimal，通常与报表单位一致。
        # 现有 DCF 把净债务与 FCF 直接相减，说明单位已在库内对齐。
        # 优先用 current_price * total_shares 估市值（元），否则用 market_cap 字段。
        equity_value = self._estimate_equity_value(company)

        debt_info = await self._get_debt_and_cash(stock_code)
        total_debt = debt_info["total_debt"]
        cash = debt_info["cash"]
        interest_expense = debt_info["interest_expense"]

        tax_rate = tax_rate_override
        if tax_rate is None:
            tax_rate = await self._estimate_tax_rate(stock_code)
        tax_rate = max(0.15, min(0.25, tax_rate if tax_rate is not None else 0.25))

        beta = beta_override if beta_override is not None else float(profile["beta"])
        beta_source = "override" if beta_override is not None else "industry_default"

        size_premium = float(profile.get("size_premium") or 0.0)
        if equity_value and equity_value < 5e9:  # <50 亿
            size_premium = max(size_premium, 0.01)
        if equity_value and equity_value < 2e9:
            size_premium = max(size_premium, 0.02)

        ke = self.rf + beta * self.erp + size_premium

        if total_debt > 0 and interest_expense > 0:
            kd = interest_expense / total_debt
            kd_source = "interest/debt"
        else:
            kd = self.default_kd
            kd_source = "default"

        # 合理性夹逼
        kd = max(0.02, min(0.15, kd))
        ke = max(0.05, min(0.25, ke))

        e = max(equity_value or 0.0, 0.0)
        d = max(total_debt, 0.0)
        v = e + d
        if v <= 0:
            e_weight, d_weight = 1.0, 0.0
            wacc = ke
            structure_source = "all_equity_fallback"
        else:
            e_weight = e / v
            d_weight = d / v
            wacc = e_weight * ke + d_weight * kd * (1.0 - tax_rate)
            structure_source = "market_weights"

        wacc = max(0.04, min(0.20, wacc))

        band = profile.get("wacc_band", (0.08, 0.12))
        in_band = band[0] <= wacc <= band[1]

        return {
            "stock_code": stock_code,
            "wacc": round(wacc, 6),
            "ke": round(ke, 6),
            "kd": round(kd, 6),
            "rf": self.rf,
            "beta": beta,
            "erp": self.erp,
            "size_premium": size_premium,
            "tax_rate": round(tax_rate, 4),
            "e_weight": round(e_weight, 4),
            "d_weight": round(d_weight, 4),
            "equity_value": equity_value,
            "total_debt": total_debt,
            "cash": cash,
            "net_debt": max(total_debt - cash, 0.0),
            "interest_expense": interest_expense,
            "industry": industry_name,
            "profile_key": profile.get("profile_key"),
            "sources": {
                "rf": "env:RISK_FREE_RATE",
                "erp": "env:EQUITY_RISK_PREMIUM",
                "beta": beta_source,
                "kd": kd_source,
                "capital_structure": structure_source,
            },
            "sanity": {
                "in_sector_band": in_band,
                "band": list(band),
                "message": None if in_band else f"WACC {wacc:.2%} 超出行业区间 {band[0]:.0%}-{band[1]:.0%}",
            },
            "exit_ev_ebitda": float(profile.get("exit_ev_ebitda") or 12.0),
            "terminal_g_cap": float(profile.get("terminal_g_cap") or 0.03),
            "methods": profile.get("methods"),
            "relative_primary": profile.get("relative_primary"),
        }

    def _estimate_equity_value(self, company: Company) -> Optional[float]:
        price = self._to_float(company.current_price)
        shares = None
        if company.total_shares:
            shares = float(company.total_shares)
        market_cap = self._to_float(company.market_cap)
        if price and shares and shares > 0:
            return price * shares
        if market_cap and market_cap > 0:
            # 库注释为万元；若数值看起来像亿元级也可能是元。启发式：
            # market_cap < 1e7 且 price*shares 不可用时，按万元×10000
            if market_cap < 1e8:
                return market_cap * 10000.0
            return market_cap
        return None

    async def _get_company(self, stock_code: str) -> Optional[Company]:
        result = await self.session.execute(
            select(Company)
            .options(selectinload(Company.industry))
            .where(Company.stock_code == stock_code)
        )
        return result.scalars().first()

    async def _get_latest_year(self, stock_code: str) -> Optional[int]:
        stmt = (
            select(FinancialData.report_date)
            .where(
                FinancialData.company_code == stock_code,
                FinancialData.report_type == ReportType.IS,
            )
            .order_by(FinancialData.report_date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        report_date = result.scalar()
        if not report_date:
            return None
        return report_date.year if hasattr(report_date, "year") else int(str(report_date)[:4])

    async def _sum_subjects(
        self,
        stock_code: str,
        codes: list[str],
        year: int,
        report_type: ReportType,
    ) -> float:
        total = 0.0
        for code in codes:
            stmt = (
                select(FinancialData.value_decimal)
                .where(
                    FinancialData.company_code == stock_code,
                    FinancialData.subject_code == code,
                    func.extract("year", FinancialData.report_date) == year,
                    FinancialData.report_type == report_type,
                )
                .order_by(FinancialData.report_date.desc())
                .limit(1)
            )
            result = await self.session.execute(stmt)
            value = result.scalar()
            if value is not None:
                total += float(value)
        return total

    async def _get_debt_and_cash(self, stock_code: str) -> Dict[str, float]:
        year = await self._get_latest_year(stock_code)
        if not year:
            return {"total_debt": 0.0, "cash": 0.0, "interest_expense": 0.0}

        short_debt = await self._sum_subjects(stock_code, self.SHORT_DEBT_CODES, year, ReportType.BS)
        long_debt = await self._sum_subjects(stock_code, self.LONG_DEBT_CODES, year, ReportType.BS)
        cash = await self._sum_subjects(stock_code, self.CASH_CODES, year, ReportType.BS)
        interest = abs(await self._sum_subjects(stock_code, self.INTEREST_CODES, year, ReportType.IS))

        return {
            "total_debt": max(short_debt + long_debt, 0.0),
            "cash": max(cash, 0.0),
            "interest_expense": interest,
        }

    async def _estimate_tax_rate(self, stock_code: str) -> Optional[float]:
        year = await self._get_latest_year(stock_code)
        if not year:
            return None
        tax = await self._sum_subjects(stock_code, self.TAX_CODES, year, ReportType.IS)
        ebt = await self._sum_subjects(stock_code, self.EBT_CODES, year, ReportType.IS)
        if ebt and ebt > 0 and tax >= 0:
            return tax / ebt
        return None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
