# -*- coding: utf-8 -*-
"""
偿债能力分析服务

移植自 leofun 项目，适配 SQLAlchemy + FastAPI。
包含流动比率、速动比率、资产负债率等核心偿债指标计算。
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..persistence.financial_models import Company, FinancialData, ReportType, ReportPeriod

logger = logging.getLogger(__name__)


class SolvencyAnalysisService:
    """
    偿债能力分析服务

    分析企业的短期和长期偿债能力，主要指标包括：
    - 流动比率：衡量短期偿债能力
    - 速动比率：剔除存货后的短期偿债能力
    - 资产负债率：衡量长期偿债能力
    - 产权比率：负债与所有者权益的比例
    """

    # 科目代码分组定义（与 account_subjects 标准编码对齐）
    SUBJECT_GROUPS = {
        "assets": {"codes": ["BSA121"], "name": "总资产"},
        "liabilities": {"codes": ["BSL112"], "name": "总负债"},
        "equity": {"codes": ["BSE012"], "name": "股东权益"},
        "current_assets": {"codes": ["BSA020"], "name": "流动资产"},
        "current_liabilities": {"codes": ["BSL022"], "name": "流动负债"},
        "inventory": {"codes": ["BSA015"], "name": "存货"},
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def analyze(
        self,
        stock_code: str,
        years: int = 5,
    ) -> Dict[str, Any]:
        """
        分析公司偿债能力

        Args:
            stock_code: 股票代码
            years: 分析年数

        Returns:
            偿债能力分析结果
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

        # 计算偿债能力指标
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

        # 优先取年报
        result = await self.session.execute(
            select(FinancialData.report_date)
            .where(
                FinancialData.company_code == stock_code,
                FinancialData.report_type == ReportType.BS,
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
                    FinancialData.report_type == ReportType.BS,
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

            # 获取各科目数据
            subjects_data = {}

            for field_name, config in self.SUBJECT_GROUPS.items():
                if "codes" in config:
                    total_result = await self.session.execute(
                        select(func.sum(FinancialData.value_decimal))
                        .where(
                            FinancialData.company_code == stock_code,
                            FinancialData.subject_code.in_(config["codes"]),
                            FinancialData.report_date == report_date,
                            FinancialData.report_type == ReportType.BS,
                        )
                    )
                    total = total_result.scalar() or Decimal("0")
                    subjects_data[field_name] = float(total)
                else:
                    subjects_data[field_name] = 0

            data.append({
                "year": year,
                "report_date": report_date.isoformat(),
                "total_assets": subjects_data.get("assets", 0),
                "total_liabilities": subjects_data.get("liabilities", 0),
                "shareholders_equity": subjects_data.get("equity", 0),
                "current_assets": subjects_data.get("current_assets", 0),
                "current_liabilities": subjects_data.get("current_liabilities", 0),
                "inventory": subjects_data.get("inventory", 0),
            })

        # 按年份升序排列
        data.sort(key=lambda x: x["year"])
        return data

    def _calculate_indicators(
        self,
        financial_data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """计算偿债能力指标"""
        indicators = []

        for data in financial_data:
            # 资产负债率 = 负债总额 / 资产总额 × 100%
            debt_asset_ratio = (
                (data["total_liabilities"] / data["total_assets"] * 100)
                if data["total_assets"]
                else 0
            )

            # 产权比率 = 负债总额 / 所有者权益 × 100%
            equity_ratio = (
                (data["total_liabilities"] / data["shareholders_equity"] * 100)
                if data["shareholders_equity"]
                else 0
            )

            # 流动比率 = 流动资产 / 流动负债
            current_ratio = (
                data["current_assets"] / data["current_liabilities"]
                if data["current_liabilities"]
                else 0
            )

            # 速动比率 = (流动资产 - 存货) / 流动负债
            quick_ratio = (
                (data["current_assets"] - data["inventory"]) / data["current_liabilities"]
                if data["current_liabilities"]
                else 0
            )

            indicators.append({
                "year": data["year"],
                "report_date": data["report_date"],
                "debt_asset_ratio": round(debt_asset_ratio, 2),
                "equity_ratio": round(equity_ratio, 2),
                "current_ratio": round(current_ratio, 2),
                "quick_ratio": round(quick_ratio, 2),
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
        metric_names = ["debt_asset_ratio", "equity_ratio", "current_ratio", "quick_ratio"]

        for metric in metric_names:
            if metric in latest and metric in earliest:
                change = latest[metric] - earliest[metric]
                change_percent = (
                    (change / earliest[metric] * 100) if earliest[metric] else 0
                )

                # 对于负债类指标，下降表示改善
                if metric in ["debt_asset_ratio", "equity_ratio"]:
                    trend = "improving" if change < 0 else "worsening" if change > 0 else "stable"
                else:
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

        # 资产负债率评估
        debt_ratio = latest["debt_asset_ratio"]
        if debt_ratio < 50:
            assessments["debt_asset_ratio"] = "excellent"
        elif debt_ratio < 70:
            assessments["debt_asset_ratio"] = "good"
        elif debt_ratio < 85:
            assessments["debt_asset_ratio"] = "warning"
        else:
            assessments["debt_asset_ratio"] = "risk"

        # 流动比率评估
        current_ratio = latest["current_ratio"]
        if current_ratio >= 2.0:
            assessments["current_ratio"] = "excellent"
        elif current_ratio >= 1.5:
            assessments["current_ratio"] = "good"
        elif current_ratio >= 1.0:
            assessments["current_ratio"] = "warning"
        else:
            assessments["current_ratio"] = "risk"

        # 速动比率评估
        quick_ratio = latest["quick_ratio"]
        if quick_ratio >= 1.0:
            assessments["quick_ratio"] = "excellent"
        elif quick_ratio >= 0.8:
            assessments["quick_ratio"] = "good"
        elif quick_ratio >= 0.5:
            assessments["quick_ratio"] = "warning"
        else:
            assessments["quick_ratio"] = "risk"

        # 综合评估
        risk_count = sum(1 for a in assessments.values() if a == "risk")
        warning_count = sum(1 for a in assessments.values() if a == "warning")
        excellent_count = sum(1 for a in assessments.values() if a == "excellent")

        if risk_count > 0:
            risk_level = "high"
            overall = "高风险"
        elif warning_count > 0:
            risk_level = "medium"
            overall = "中风险"
        elif excellent_count >= 2:
            risk_level = "low"
            overall = "优秀"
        else:
            risk_level = "low"
            overall = "良好"

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
            "summary": f"公司{latest['year']}年偿债能力评估为{overall}，{trend_desc}",
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
                if metric == "debt_asset_ratio":
                    recommendations.append("资产负债率过高，建议减少负债或增加资产")
                elif metric == "current_ratio":
                    recommendations.append("流动比率偏低，建议增加流动资产或减少流动负债")
                elif metric == "quick_ratio":
                    recommendations.append("速动比率偏低，建议改善存货管理或增加速动资产")
            elif assessment == "warning":
                if metric == "debt_asset_ratio":
                    recommendations.append("资产负债率处于临界值，建议密切关注债务结构")
                elif metric == "current_ratio":
                    recommendations.append("流动比率需要改善，建议优化营运资金管理")

        return recommendations or ["各项偿债能力指标表现良好，建议保持现状"]

    def _company_to_dict(self, company: Company) -> Dict[str, Any]:
        """转换公司对象为字典"""
        return {
            "stock_code": company.stock_code,
            "stock_name": company.stock_name,
            "company_name": company.company_name,
        }
