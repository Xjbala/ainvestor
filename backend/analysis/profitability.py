# -*- coding: utf-8 -*-
"""
盈利能力分析服务

包含 ROA、ROE、毛利率、营业利润率等核心盈利指标计算。
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..persistence.financial_models import Company, FinancialData, ReportType, ReportPeriod

logger = logging.getLogger(__name__)


class ProfitabilityAnalysisService:
    """
    盈利能力分析服务

    分析企业的盈利能力，主要指标包括：
    - 毛利率：衡量产品盈利能力
    - 营业利润率：衡量经营盈利水平
    - ROA（总资产报酬率）：衡量资产使用效率
    - ROE（净资产收益率）：衡量股东权益回报
    """

    # 科目代码分组定义（与 account_subjects 标准编码对齐）
    SUBJECT_GROUPS = {
        "total_revenue": {"codes": ["ISI001"], "name": "营业收入", "report_type": "IS"},
        "operating_cost": {"codes": ["ISC001"], "name": "营业成本", "report_type": "IS"},
        "operating_profit": {"codes": ["ISF016"], "name": "营业利润", "report_type": "IS"},
        "net_profit": {"codes": ["ISF021"], "name": "净利润", "report_type": "IS"},
        # 使用汇总科目，避免 prefix 把明细科目加总导致重复计算
        "total_assets": {"codes": ["BSA121"], "name": "总资产", "report_type": "BS"},
        "shareholders_equity": {"codes": ["BSE012"], "name": "股东权益", "report_type": "BS"},
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def analyze(
        self,
        stock_code: str,
        years: int = 5,
    ) -> Dict[str, Any]:
        """
        分析公司盈利能力

        Args:
            stock_code: 股票代码
            years: 分析年数

        Returns:
            盈利能力分析结果
        """
        # 获取公司信息
        result = await self.session.execute(
            select(Company).where(Company.stock_code == stock_code)
        )
        company = result.scalar_one_or_none()

        if not company:
            return {
                "error": f"公司不存在: {stock_code}",
                "company": None,
                "indicators": [],
                "trend_analysis": {},
                "conclusion": {},
            }

        # 获取财务数据
        financial_data = await self._get_financial_data(stock_code, years)

        if not financial_data:
            return {
                "company": self._company_to_dict(company),
                "indicators": [],
                "trend_analysis": {},
                "conclusion": {
                    "summary": "未找到相关财务数据",
                    "risk_level": "unknown",
                    "recommendations": ["请检查数据完整性"],
                },
            }

        # 计算盈利能力指标
        indicators = self._calculate_indicators(financial_data)

        # 计算趋势分析
        trend_analysis = self._calculate_trend_analysis(indicators)

        # 生成分析结论
        conclusion = self._generate_conclusion(indicators, trend_analysis)

        return {
            "company": self._company_to_dict(company),
            "analysis_period": {
                "years": years,
                "data_years": [d["year"] for d in financial_data],
            },
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

        # 优先取年报；年报不足时再回退到全部报告期
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

        if not report_dates:
            return []

        for report_date in report_dates:
            year = report_date.year
            subjects_data = {}

            # 获取利润表 / 资产负债表数据
            for field_name, config in self.SUBJECT_GROUPS.items():
                try:
                    report_type = ReportType(config.get("report_type", "IS"))
                    query_date = report_date
                    if report_type == ReportType.BS:
                        bs_result = await self.session.execute(
                            select(FinancialData.report_date)
                            .where(
                                FinancialData.company_code == stock_code,
                                FinancialData.report_type == ReportType.BS,
                                FinancialData.report_date <= report_date,
                            )
                            .order_by(FinancialData.report_date.desc())
                            .limit(1)
                        )
                        query_date = bs_result.scalar()
                        if not query_date:
                            subjects_data[field_name] = 0
                            continue

                    if "codes" in config:
                        total_result = await self.session.execute(
                            select(func.sum(FinancialData.value_decimal))
                            .where(
                                FinancialData.company_code == stock_code,
                                FinancialData.subject_code.in_(config["codes"]),
                                FinancialData.report_date == query_date,
                                FinancialData.report_type == report_type,
                            )
                        )
                        total = total_result.scalar() or Decimal("0")
                        subjects_data[field_name] = float(total)
                    else:
                        subjects_data[field_name] = 0

                except Exception as e:
                    logger.error(f"Error fetching {field_name}: {e}")
                    subjects_data[field_name] = 0

            data.append({
                "year": year,
                "report_date": report_date.isoformat(),
                "total_revenue": subjects_data.get("total_revenue", 0),
                "operating_cost": subjects_data.get("operating_cost", 0),
                "operating_profit": subjects_data.get("operating_profit", 0),
                "net_profit": subjects_data.get("net_profit", 0),
                "total_assets": subjects_data.get("total_assets", 0),
                "shareholders_equity": subjects_data.get("shareholders_equity", 0),
            })

        # 按年份升序排列
        data.sort(key=lambda x: x["year"])
        return data

    def _calculate_indicators(
        self,
        financial_data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """计算盈利能力指标"""
        indicators = []

        for i, data in enumerate(financial_data):
            # 毛利率 = (营业收入 - 营业成本) / 营业收入 × 100%
            gross_margin = (
                ((data["total_revenue"] - data["operating_cost"]) / data["total_revenue"] * 100)
                if data["total_revenue"]
                else 0
            )

            # 营业利润率 = 营业利润 / 营业收入 × 100%
            operating_margin = (
                (data["operating_profit"] / data["total_revenue"] * 100)
                if data["total_revenue"] and data["operating_profit"]
                else 0
            )

            # ROA = 净利润 / 平均总资产 × 100%
            if i == 0:
                avg_assets = data["total_assets"]
            else:
                prev_data = financial_data[i - 1]
                avg_assets = (data["total_assets"] + prev_data["total_assets"]) / 2

            roa = (data["net_profit"] / avg_assets * 100) if avg_assets else 0

            # ROE = 净利润 / 平均股东权益 × 100%
            if i == 0:
                avg_equity = data["shareholders_equity"]
            else:
                prev_data = financial_data[i - 1]
                avg_equity = (data["shareholders_equity"] + prev_data["shareholders_equity"]) / 2

            roe = (data["net_profit"] / avg_equity * 100) if avg_equity else 0

            indicators.append({
                "year": data["year"],
                "report_date": data["report_date"],
                "gross_margin": round(gross_margin, 2),
                "operating_margin": round(operating_margin, 2),
                "roa": round(roa, 2),
                "roe": round(roe, 2),
            })

        return indicators

    def _calculate_trend_analysis(
        self,
        indicators: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """计算趋势分析"""
        if len(indicators) < 2:
            return {}

        earliest = indicators[0]
        latest = indicators[-1]

        trend_analysis = {}
        metric_names = ["gross_margin", "operating_margin", "roa", "roe"]

        for metric in metric_names:
            if metric in latest and metric in earliest:
                change = latest[metric] - earliest[metric]
                change_percent = (
                    (change / abs(earliest[metric]) * 100) if earliest[metric] else 0
                )

                trend = "improving" if change > 0 else "worsening" if change < 0 else "stable"

                trend_analysis[metric] = {
                    "latest_value": latest[metric],
                    "earliest_value": earliest[metric],
                    "change": round(change, 2),
                    "change_percent": round(change_percent, 2),
                    "trend": trend,
                }

        return trend_analysis

    def _generate_conclusion(
        self,
        indicators: List[Dict[str, Any]],
        trend_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """生成分析结论"""
        if not indicators:
            return {"summary": "无足够数据进行分析", "risk_level": "unknown"}

        latest = indicators[-1]
        assessments = {}

        # 毛利率评估（阈值可根据行业调整，当前为通用标准）
        gross_margin = latest["gross_margin"]
        if gross_margin >= 40:
            assessments["gross_margin"] = "excellent"
        elif gross_margin >= 25:
            assessments["gross_margin"] = "good"
        elif gross_margin >= 15:
            assessments["gross_margin"] = "warning"
        else:
            assessments["gross_margin"] = "risk"

        # ROA 评估
        roa = latest["roa"]
        if roa >= 15:
            assessments["roa"] = "excellent"
        elif roa >= 8:
            assessments["roa"] = "good"
        elif roa >= 3:
            assessments["roa"] = "warning"
        else:
            assessments["roa"] = "risk"

        # ROE 评估
        roe = latest["roe"]
        if roe >= 20:
            assessments["roe"] = "excellent"
        elif roe >= 12:
            assessments["roe"] = "good"
        elif roe >= 6:
            assessments["roe"] = "warning"
        else:
            assessments["roe"] = "risk"

        # 综合评估
        risk_count = sum(1 for a in assessments.values() if a == "risk")
        warning_count = sum(1 for a in assessments.values() if a == "warning")
        excellent_count = sum(1 for a in assessments.values() if a == "excellent")

        if risk_count > 0:
            risk_level = "high"
            overall = "盈利性较差"
        elif warning_count > 0:
            risk_level = "medium"
            overall = "盈利性一般"
        elif excellent_count >= 2:
            risk_level = "low"
            overall = "盈利性优秀"
        else:
            risk_level = "low"
            overall = "盈利性良好"

        # 趋势描述
        improving = sum(1 for t in trend_analysis.values() if t.get("trend") == "improving")
        worsening = sum(1 for t in trend_analysis.values() if t.get("trend") == "worsening")

        if improving >= 2:
            trend_desc = "整体呈改善趋势"
        elif worsening >= 2:
            trend_desc = "整体呈下降趋势"
        else:
            trend_desc = "整体表现相对稳定"

        return {
            "summary": f"公司{latest['year']}年盈利能力评估为{overall}，{trend_desc}",
            "risk_level": risk_level,
            "detailed_assessment": assessments,
            "recommendations": self._generate_recommendations(assessments, trend_analysis),
        }

    def _generate_recommendations(
        self,
        assessments: Dict[str, str],
        trend_analysis: Dict[str, Any],
    ) -> List[str]:
        """生成建议"""
        recommendations = []

        for metric, assessment in assessments.items():
            if assessment == "risk":
                if metric == "gross_margin":
                    recommendations.append("毛利率偏低，建议调整产品结构或降低成本")
                elif metric == "roa":
                    recommendations.append("资产收益率偏低，建议提高资产使用效率")
                elif metric == "roe":
                    recommendations.append("净资产收益率偏低，建议优化资本结构")
            elif assessment == "warning":
                if metric == "gross_margin":
                    recommendations.append("毛利率处于临界值，建议关注成本控制")
                elif metric == "roa":
                    recommendations.append("资产使用效率有待提升")
                elif metric == "roe":
                    recommendations.append("股东权益回报需要改善")

        return recommendations or ["各项盈利能力指标表现良好，建议保持现状"]

    def _company_to_dict(self, company: Company) -> Dict[str, Any]:
        """转换公司对象为字典"""
        return {
            "stock_code": company.stock_code,
            "stock_name": company.stock_name,
            "company_name": company.company_name,
        }
