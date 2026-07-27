# -*- coding: utf-8 -*-
"""
营运能力分析服务

分析企业的资产运营效率。
"""

from decimal import Decimal
from typing import Any, Dict, List
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..persistence.financial_models import Company, FinancialData, ReportType, ReportPeriod

logger = logging.getLogger(__name__)


class OperatingAnalysisService:
    """
    营运能力分析服务

    分析企业的运营效率，主要指标包括：
    - 总资产周转率
    - 应收账款周转率
    - 存货周转率
    - 流动资产周转率
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def analyze(
        self,
        stock_code: str,
        years: int = 5,
    ) -> Dict[str, Any]:
        """分析公司营运能力"""
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
                "conclusion": {"summary": "数据不足，无法计算周转率"},
            }

        # 计算营运指标
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

        # 优先取年报，保证周转率同比可比
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

            # 获取营业收入（ISI001）
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

            # 获取营业成本（ISC001）
            cost_result = await self.session.execute(
                select(func.sum(FinancialData.value_decimal))
                .where(
                    FinancialData.company_code == stock_code,
                    FinancialData.subject_code.in_(["ISC001"]),
                    FinancialData.report_date == report_date,
                    FinancialData.report_type == ReportType.IS,
                )
            )
            cost = float(cost_result.scalar() or 0)

            # 获取总资产（BSA121）
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

            # 获取流动资产（BSA020 流动资产合计）
            current_assets_result = await self.session.execute(
                select(func.sum(FinancialData.value_decimal))
                .where(
                    FinancialData.company_code == stock_code,
                    FinancialData.subject_code.in_(["BSA020"]),
                    FinancialData.report_date == report_date,
                    FinancialData.report_type == ReportType.BS,
                )
            )
            current_assets = float(current_assets_result.scalar() or 0)

            # 获取应收账款（应收票据BSA006 + 应收账款BSA007）
            receivables_result = await self.session.execute(
                select(func.sum(FinancialData.value_decimal))
                .where(
                    FinancialData.company_code == stock_code,
                    FinancialData.subject_code.in_(["BSA006", "BSA007"]),
                    FinancialData.report_date == report_date,
                    FinancialData.report_type == ReportType.BS,
                )
            )
            receivables = float(receivables_result.scalar() or 0)

            # 获取存货（BSA015）
            inventory_result = await self.session.execute(
                select(func.sum(FinancialData.value_decimal))
                .where(
                    FinancialData.company_code == stock_code,
                    FinancialData.subject_code.in_(["BSA015"]),
                    FinancialData.report_date == report_date,
                    FinancialData.report_type == ReportType.BS,
                )
            )
            inventory = float(inventory_result.scalar() or 0)

            data.append({
                "year": year,
                "revenue": revenue,
                "cost": cost,
                "total_assets": total_assets,
                "current_assets": current_assets,
                "receivables": receivables,
                "inventory": inventory,
            })

        data.sort(key=lambda x: x["year"])
        return data

    def _calculate_indicators(
        self,
        financial_data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """计算营运指标"""
        indicators = []

        for i in range(1, len(financial_data)):
            current = financial_data[i]
            previous = financial_data[i - 1]

            # 平均资产
            avg_assets = (current["total_assets"] + previous["total_assets"]) / 2
            avg_current_assets = (current["current_assets"] + previous["current_assets"]) / 2
            avg_receivables = (current["receivables"] + previous["receivables"]) / 2
            avg_inventory = (current["inventory"] + previous["inventory"]) / 2

            # 总资产周转率 = 营业收入 / 平均总资产
            asset_turnover = current["revenue"] / avg_assets if avg_assets else 0

            # 流动资产周转率 = 营业收入 / 平均流动资产
            current_asset_turnover = current["revenue"] / avg_current_assets if avg_current_assets else 0

            # 应收账款周转率 = 营业收入 / 平均应收账款
            receivables_turnover = current["revenue"] / avg_receivables if avg_receivables else 0

            # 存货周转率 = 营业成本 / 平均存货
            inventory_turnover = current["cost"] / avg_inventory if avg_inventory else 0

            indicators.append({
                "year": current["year"],
                "asset_turnover": round(asset_turnover, 2),
                "current_asset_turnover": round(current_asset_turnover, 2),
                "receivables_turnover": round(receivables_turnover, 2),
                "inventory_turnover": round(inventory_turnover, 2),
            })

        return indicators

    def _calculate_trend_analysis(
        self,
        indicators: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """计算趋势"""
        if not indicators:
            return {}

        # 平均周转率
        avg_asset_turnover = sum(i["asset_turnover"] for i in indicators) / len(indicators)

        return {
            "avg_asset_turnover": round(avg_asset_turnover, 2),
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
        asset_turnover = latest["asset_turnover"]

        if asset_turnover >= 1.5:
            level = "优秀"
            risk_level = "low"
        elif asset_turnover >= 1.0:
            level = "良好"
            risk_level = "low"
        elif asset_turnover >= 0.5:
            level = "一般"
            risk_level = "medium"
        else:
            level = "较差"
            risk_level = "high"

        return {
            "summary": f"公司{latest['year']}年营运能力评估为{level}",
            "risk_level": risk_level,
            "recommendations": self._generate_recommendations(asset_turnover),
        }

    def _generate_recommendations(self, asset_turnover: float) -> List[str]:
        """生成建议"""
        if asset_turnover >= 1.5:
            return ["资产运营效率高，继续保持", "可考虑适度扩大资产规模"]
        elif asset_turnover >= 1.0:
            return ["资产运营良好", "关注存货和应收账款管理"]
        elif asset_turnover >= 0.5:
            return ["资产使用效率有待提升", "优化资产结构，处置闲置资产"]
        else:
            return ["资产运营效率偏低", "需重点改善资产管理，提高周转效率"]

    def _company_to_dict(self, company: Company) -> Dict[str, Any]:
        """转换公司对象"""
        return {
            "stock_code": company.stock_code,
            "stock_name": company.stock_name,
            "company_name": company.company_name,
        }
