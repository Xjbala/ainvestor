# -*- coding: utf-8 -*-
"""
行业竞争分析服务

用已有财务数据计算行业集中度指标（CR3/CR5/HHI）、竞争态势、周期判断。
不需要新增数据采集，完全基于已有的 financial_data 表计算。
"""

import logging
from typing import Dict, List, Optional
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..persistence.financial_models import (
    FinancialData, ReportType, ReportPeriod, Company, Industry, AccountSubject
)

logger = logging.getLogger(__name__)


class IndustryCompetitionService:
    """
    行业竞争格局分析服务

    基于已有财务数据，计算：
    1. 行业集中度（CR3, CR5, HHI）
    2. 毛利率离散度（判断价格竞争强度）
    3. 行业增速趋势
    4. 产能扩张信号
    5. 周期阶段判断
    """

    # 关键科目代码映射
    REVENUE_CODE = "6001"   # 营业收入
    NET_PROFIT_CODE = "6016"  # 净利润
    TOTAL_ASSETS_CODE = "6001"  # 总资产（需要确认实际代码）
    CONSTRUCTION_IN_PROGRESS_CODE = "1020"  # 在建工程
    INVENTORY_CODE = "1030"  # 存货
    TOTAL_COST_CODE = "6020"  # 营业成本

    async def analyze_industry(
        self,
        session: AsyncSession,
        industry_id: int,
        years: int = 5,
    ) -> Dict:
        """
        分析指定行业的竞争格局

        Args:
            session: 数据库会话
            industry_id: 行业 ID
            years: 分析年数

        Returns:
            行业竞争分析结果
        """
        # 1. 获取该行业所有公司
        stmt = select(Company).where(
            Company.industry_id == industry_id,
            Company.status == "active",
        )
        result = await session.execute(stmt)
        companies = result.scalars().all()

        if not companies:
            return {"error": f"行业 ID {industry_id} 下无活跃公司"}

        company_codes = [c.stock_code for c in companies]

        # 2. 获取各公司近年营收数据
        revenue_data = await self._get_company_metric(
            session, company_codes, "revenue", years
        )

        # 3. 计算集中度指标
        cr3, cr5, hhi = self._calculate_concentration(revenue_data)

        # 4. 计算毛利率指标
        gdp_data = await self._get_gdp_by_year(session, company_codes, years)
        gdp_mean, gdp_std = self._calc_gdp_stats(gdp_data)

        # 5. 行业增速趋势
        revenue_growth_trend = self._calc_growth_trend(
            [d.get("revenue", 0) for d in revenue_data.values()]
        )

        # 6. 产能扩张信号
        wip_growth = await self._calc_wip_vs_revenue(session, company_codes)

        # 7. 综合判断
        competition_level = self._judge_competition(cr5, gdp_std)
        cycle_phase = self._judge_cycle(revenue_growth_trend, wip_growth)

        return {
            "industry_id": industry_id,
            "company_count": len(companies),
            "cr3": round(cr3, 2) if cr3 else None,
            "cr5": round(cr5, 2) if cr5 else None,
            "hhi": round(hhi, 2) if hhi else None,
            "gdp_mean": round(gdp_mean, 2) if gdp_mean else None,
            "gdp_std": round(gdp_std, 2) if gdp_std else None,
            "revenue_growth_trend": revenue_growth_trend,
            "wip_vs_revenue_growth": round(wip_growth, 2) if wip_growth else None,
            "competition_level": competition_level,
            "cycle_phase": cycle_phase,
            "interpretation": self._generate_interpretation(
                cr3, cr5, hhi, gdp_mean, gdp_std,
                revenue_growth_trend, competition_level, cycle_phase
            ),
        }

    async def _get_company_metric(
        self,
        session: AsyncSession,
        stock_codes: List[str],
        metric: str,
        years: int,
    ) -> Dict[str, dict]:
        """获取公司某指标的历年数据"""
        # 简化：直接返回空字典，实际需要根据科目代码查 financial_data 表
        # 这里先返回占位数据
        result = {}
        for code in stock_codes[:20]:  # 限制数量避免查询过大
            result[code] = {"revenue": 0}
        return result

    def _calculate_concentration(
        self, revenue_data: Dict[str, dict]
    ) -> tuple:
        """
        计算 CR3, CR5, HHI

        Args:
            revenue_data: {stock_code: {"revenue": amount}}

        Returns:
            (cr3, cr5, hhi)
        """
        revenues = [d.get("revenue", 0) for d in revenue_data.values()]
        total = sum(revenues)

        if total == 0 or len(revenues) < 3:
            return None, None, None

        # 按营收降序排列
        sorted_revs = sorted(revenues, reverse=True)

        # CR3 / CR5
        cr3 = sum(sorted_revs[:3]) / total * 100
        cr5 = sum(sorted_revs[:min(5, len(sorted_revs))]) / total * 100

        # HHI = Σ(市占率²)
        market_shares = [r / total * 100 for r in sorted_revs]
        hhi = sum(ms ** 2 for ms in market_shares)

        return cr3, cr5, hhi

    async def _get_gdp_by_year(
        self,
        session: AsyncSession,
        stock_codes: List[str],
        years: int,
    ) -> List[dict]:
        """获取各年毛利率数据"""
        return [{"year": 2024 - i, "gdps": []} for i in range(min(years, 5))]

    def _calc_gdp_stats(self, gdp_data: List[dict]) -> tuple:
        """计算毛利率均值和标准差"""
        all_gdps = []
        for year_data in gdp_data:
            all_gdps.extend(year_data.get("gdps", []))

        if not all_gdps:
            return None, None

        mean = sum(all_gdps) / len(all_gdps)
        variance = sum((x - mean) ** 2 for x in all_gdps) / len(all_gdps)
        std = variance ** 0.5

        return mean, std

    def _calc_growth_trend(self, revenue_series: List[float]) -> str:
        """判断营收增速趋势"""
        if len(revenue_series) < 3:
            return "insufficient_data"

        # 简单判断：最近两年是否持续增长
        if revenue_series[-1] > revenue_series[-2] > revenue_series[-3]:
            return "accelerating"
        elif revenue_series[-1] < revenue_series[-2] < revenue_series[-3]:
            return "declining"
        return "stable"

    async def _calc_wip_vs_revenue(
        self, session: AsyncSession, stock_codes: List[str]
    ) -> float:
        """
        计算在建工程增速 - 营收增速

        正值表示扩产速度快于需求增长，可能是产能过剩的信号
        """
        return 0.0  # 占位

    def _judge_competition(self, cr5: Optional[float], gdp_std: Optional[float]) -> str:
        """
        判断竞争程度

        CR5 < 20%: 充分竞争
        CR5 20-50%: 寡头竞争
        CR5 > 50%: 垄断/高度集中

        GDP 标准差小说明产品同质化，价格竞争激烈
        """
        if cr5 is None:
            return "unknown"

        if cr5 > 50:
            return "monopoly"
        elif cr5 > 20:
            return "oligopoly"
        else:
            return "competitive"

    def _judge_cycle(self, growth_trend: str, wip_gap: float) -> str:
        """
        判断周期阶段

        加速增长 + 产能扩张 = 扩张期
        减速增长 + 产能过剩 = 衰退期
        """
        if growth_trend == "accelerating":
            return "expansion"
        elif growth_trend == "declining":
            return "decline"
        return "stable"

    def _generate_interpretation(
        self,
        cr3, cr5, hhi,
        gdp_mean, gdp_std,
        growth_trend,
        competition_level,
        cycle_phase,
    ) -> str:
        """生成人类可读的行业竞争分析解读"""
        parts = []

        if cr5:
            if cr5 > 50:
                parts.append(f"行业集中度较高（CR5={cr5:.1f}%），呈现寡头或垄断格局")
            elif cr5 > 20:
                parts.append(f"行业有一定集中度（CR5={cr5:.1f}%），属于寡头竞争")
            else:
                parts.append(f"行业集中度较低（CR5={cr5:.1f}%），竞争较为充分")

        if gdp_std is not None:
            if gdp_std < 3:
                parts.append("行业毛利率差异小，产品同质化严重，价格竞争激烈")
            elif gdp_std < 8:
                parts.append("行业毛利率有一定差异，部分公司有竞争优势")
            else:
                parts.append("行业毛利率差异大，公司分化明显")

        if growth_trend:
            parts.append(f"行业增速趋势：{growth_trend}")

        if competition_level:
            parts.append(f"竞争程度：{competition_level}")

        if cycle_phase:
            parts.append(f"周期阶段：{cycle_phase}")

        return "；".join(parts) if parts else "数据不足，无法判断"
