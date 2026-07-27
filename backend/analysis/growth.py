# -*- coding: utf-8 -*-
"""
发展能力分析服务

分析企业的成长和发展潜力。
"""

from decimal import Decimal
from typing import Any, Dict, List
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..persistence.financial_models import Company, FinancialData, ReportType, ReportPeriod

logger = logging.getLogger(__name__)


class GrowthAnalysisService:
    """
    发展能力分析服务

    分析企业的成长能力，主要指标包括：
    - 营业收入增长率
    - 净利润增长率
    - 总资产增长率
    - 净资产增长率
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def analyze(
        self,
        stock_code: str,
        years: int = 5,
    ) -> Dict[str, Any]:
        """分析公司发展能力"""
        # 获取公司信息
        result = await self.session.execute(
            select(Company).where(Company.stock_code == stock_code)
        )
        company = result.scalar_one_or_none()

        if not company:
            return {"error": f"公司不存在: {stock_code}"}

        # 获取财务数据
        financial_data = await self._get_financial_data(stock_code, years)

        if len(financial_data) < 2:
            return {
                "company": self._company_to_dict(company),
                "indicators": [],
                "conclusion": {"summary": "数据不足，无法计算增长率"},
            }

        # 计算增长指标
        indicators = self._calculate_indicators(financial_data)

        # 计算趋势
        trend_analysis = self._calculate_trend_analysis(indicators)

        # 生成结论
        conclusion = self._generate_conclusion(indicators, trend_analysis)

        return {
            "company": self._company_to_dict(company),
            "analysis_period": {"years": years},
            "indicators": indicators,
            "trend_analysis": trend_analysis,
            "conclusion": conclusion,
        }

    async def _get_financial_data(
        self,
        stock_code: str,
        years: int,
    ) -> List[Dict[str, Any]]:
        """获取财务数据"""
        data = []

        # 优先取年报，保证同比可比
        result = await self.session.execute(
            select(FinancialData.report_date)
            .where(
                FinancialData.company_code == stock_code,
                FinancialData.report_type == ReportType.IS,
                FinancialData.report_period == ReportPeriod.ANNUAL,
            )
            .distinct()
            .order_by(FinancialData.report_date.desc())
            .limit(years)
        )
        report_dates = [row[0] for row in result.fetchall()]
        if not report_dates:
            result = await self.session.execute(
                select(FinancialData.report_date)
                .where(
                    FinancialData.company_code == stock_code,
                    FinancialData.report_type == ReportType.IS,
                )
                .distinct()
                .order_by(FinancialData.report_date.desc())
                .limit(years)
            )
            report_dates = [row[0] for row in result.fetchall()]

        for report_date in report_dates:
            year = report_date.year

            # 获取收入（营业收入 ISI001）
            revenue_result = await self.session.execute(
                select(func.sum(FinancialData.value_decimal))
                .where(
                    FinancialData.company_code == stock_code,
                    FinancialData.subject_code.in_(["ISI001"]),
                    FinancialData.report_date == report_date,
                    FinancialData.report_type == ReportType.IS,
                )
            )
            revenue = float(revenue_result.scalar() or 0)

            # 获取净利润（ISF021）
            profit_result = await self.session.execute(
                select(func.sum(FinancialData.value_decimal))
                .where(
                    FinancialData.company_code == stock_code,
                    FinancialData.subject_code.in_(["ISF021"]),
                    FinancialData.report_date == report_date,
                    FinancialData.report_type == ReportType.IS,
                )
            )
            net_profit = float(profit_result.scalar() or 0)

            # 获取总资产（资产总计 BSA121）
            assets_result = await self.session.execute(
                select(func.sum(FinancialData.value_decimal))
                .where(
                    FinancialData.company_code == stock_code,
                    FinancialData.subject_code.in_(["BSA121"]),
                    FinancialData.report_date == report_date,
                    FinancialData.report_type == ReportType.BS,
                )
            )
            total_assets = float(assets_result.scalar() or 0)

            # 获取净资产（所有者权益合计 BSE012）
            equity_result = await self.session.execute(
                select(func.sum(FinancialData.value_decimal))
                .where(
                    FinancialData.company_code == stock_code,
                    FinancialData.subject_code.in_(["BSE012"]),
                    FinancialData.report_date == report_date,
                    FinancialData.report_type == ReportType.BS,
                )
            )
            net_assets = float(equity_result.scalar() or 0)

            data.append({
                "year": year,
                "revenue": revenue,
                "net_profit": net_profit,
                "total_assets": total_assets,
                "net_assets": net_assets,
            })

        data.sort(key=lambda x: x["year"])
        return data

    def _calculate_indicators(
        self,
        financial_data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """计算增长指标"""
        indicators = []

        for i in range(1, len(financial_data)):
            current = financial_data[i]
            previous = financial_data[i - 1]

            # 营业收入增长率
            revenue_growth = (
                ((current["revenue"] - previous["revenue"]) / previous["revenue"] * 100)
                if previous["revenue"]
                else 0
            )

            # 净利润增长率
            profit_growth = (
                ((current["net_profit"] - previous["net_profit"]) / abs(previous["net_profit"]) * 100)
                if previous["net_profit"]
                else 0
            )

            # 总资产增长率
            assets_growth = (
                ((current["total_assets"] - previous["total_assets"]) / previous["total_assets"] * 100)
                if previous["total_assets"]
                else 0
            )

            # 净资产增长率
            equity_growth = (
                ((current["net_assets"] - previous["net_assets"]) / previous["net_assets"] * 100)
                if previous["net_assets"]
                else 0
            )

            indicators.append({
                "year": current["year"],
                "revenue_growth": round(revenue_growth, 2),
                "profit_growth": round(profit_growth, 2),
                "assets_growth": round(assets_growth, 2),
                "equity_growth": round(equity_growth, 2),
            })

        return indicators

    def _calculate_trend_analysis(
        self,
        indicators: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """计算趋势"""
        if not indicators:
            return {}

        # 计算平均增长率
        avg_revenue_growth = sum(i["revenue_growth"] for i in indicators) / len(indicators)
        avg_profit_growth = sum(i["profit_growth"] for i in indicators) / len(indicators)

        return {
            "avg_revenue_growth": round(avg_revenue_growth, 2),
            "avg_profit_growth": round(avg_profit_growth, 2),
            "growth_stability": "stable" if all(i["revenue_growth"] > 0 for i in indicators) else "volatile",
        }

    def _generate_conclusion(
        self,
        indicators: List[Dict[str, Any]],
        trend_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """生成结论"""
        if not indicators:
            return {"summary": "数据不足"}

        latest = indicators[-1]
        avg_growth = trend_analysis.get("avg_revenue_growth", 0)

        if avg_growth >= 20:
            level = "高速成长"
            risk_level = "low"
        elif avg_growth >= 10:
            level = "稳健成长"
            risk_level = "low"
        elif avg_growth >= 0:
            level = "低速成长"
            risk_level = "medium"
        else:
            level = "负增长"
            risk_level = "high"

        return {
            "summary": f"公司{latest['year']}年发展能力评估为{level}",
            "risk_level": risk_level,
            "recommendations": self._generate_recommendations(avg_growth),
        }

    def _generate_recommendations(self, avg_growth: float) -> List[str]:
        """生成建议"""
        if avg_growth >= 20:
            return ["高速增长阶段，注意控制风险", "考虑优化资本结构支持扩张"]
        elif avg_growth >= 10:
            return ["增长稳健，可考虑适度扩张", "关注市场份额提升机会"]
        elif avg_growth >= 0:
            return ["增长放缓，建议寻找新增长点", "优化成本结构提升盈利"]
        else:
            return ["业务收缩，需制定应对策略", "考虑业务转型或战略调整"]

    def _company_to_dict(self, company: Company) -> Dict[str, Any]:
        """转换公司对象"""
        return {
            "stock_code": company.stock_code,
            "stock_name": company.stock_name,
            "company_name": company.company_name,
        }
