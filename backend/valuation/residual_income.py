# -*- coding: utf-8 -*-
"""
剩余收益估值服务

基于 leofun 项目的专业剩余收益估值实现。
使用剩余收益模型（Residual Income Model）估算企业价值。

核心公式：
剩余收益 (RI) = 每股收益 - (股权成本 × 期初每股净资产)
每股内在价值 = 当前每股净资产 + 预测期剩余收益现值 + 终值现值

该方法特别适合：
- 高增长但分红率较低的公司
- ROE持续高于股权成本的公司
- 账面价值较为稳定的公司
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..persistence.financial_models import Company, FinancialData, ReportType, ReportPeriod
from .query_helpers import calendar_year_bounds

logger = logging.getLogger(__name__)


class ResidualIncomeService:
    """
    剩余收益估值服务

    采用每股剩余收益模型：
    1. 预测期（通常5年）
    2. 永续增长阶段

    特性：
    - 基于每股数据的精确计算
    - 完整的ROE和剩余收益预测
    - 详细的计算步骤记录
    - 参数假设透明化
    - 自动投资评级生成
    """

    # 默认参数
    DEFAULT_PARAMS = {
        "cost_of_equity": 0.09,        # 股权成本率
        "growth_rate": 0.15,           # 预测期增长率
        "terminal_growth_rate": 0.03,  # 永续增长率
        "projection_years": 5,         # 预测年数
        "payout_ratio": 0.30,          # 股利支付率
        "scenario": "n_years_re_zero" # 默认场景：N年后RE=0
    }

    # 财务科目代码映射
    SUBJECT_CODES = {
        # 利润表科目
        'revenue': ['ISI001'],              # 营业收入
        'net_income': ['ISF021'],           # 净利润

        # 资产负债表科目
        'total_assets': ['BSA121'],         # 资产总计
        'total_liabilities': ['BSL112'],    # 负债合计
        'shareholders_equity': ['BSE010'],  # 归属于母公司所有者权益合计
        'shares_outstanding': ['BSE001'],   # 实收资本（或股本）
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = logger

    async def valuate(
        self,
        stock_code: str,
        valuation_date: Optional[date] = None,
        params: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        执行剩余收益估值

        Args:
            stock_code: 股票代码
            valuation_date: 估值日期（可选，默认使用最新报告期）
            params: 自定义参数（覆盖默认值）

        Returns:
            包含估值结果的字典
        """
        try:
            # 合并参数
            calc_params = {**self.DEFAULT_PARAMS, **(params or {})}

            cost_of_equity = Decimal(str(calc_params["cost_of_equity"]))
            growth_rate = Decimal(str(calc_params["growth_rate"]))
            terminal_growth_rate = Decimal(str(calc_params["terminal_growth_rate"]))
            projection_years = int(calc_params["projection_years"])
            payout_ratio = Decimal(str(calc_params["payout_ratio"]))

            # 1. 获取公司信息
            company = await self._get_company(stock_code)
            if not company:
                return {"error": f"公司不存在: {stock_code}"}

            # 2. 确定基准报告期
            base_report = await self._get_latest_report_info(stock_code)
            if not base_report:
                return {
                    "company": self._company_to_dict(company),
                    "error": "无法获取财务报告日期",
                }

            report_date = base_report["report_date"]

            # 确保 report_date 是 date 对象
            if isinstance(report_date, str):
                from datetime import datetime
                report_date = datetime.strptime(report_date, "%Y-%m-%d").date()
            elif isinstance(report_date, dict):
                # 如果是字典，尝试从中提取日期
                report_date = report_date.get("report_date", report_date)
                if isinstance(report_date, str):
                    from datetime import datetime
                    report_date = datetime.strptime(report_date, "%Y-%m-%d").date()

            base_year = report_date.year

            # 3. 获取基准财务数据
            base_financials = await self._get_base_financials(stock_code, base_year)
            if not base_financials:
                return {
                    "company": self._company_to_dict(company),
                    "error": f"无法获取 {base_year} 年的财务数据",
                }

            # 4. 执行剩余收益估值计算
            # 确保 valuation_date 是 date 对象
            if valuation_date is None:
                valuation_date = report_date
            elif isinstance(valuation_date, str):
                from datetime import datetime
                valuation_date = datetime.strptime(valuation_date, "%Y-%m-%d").date()
            elif isinstance(valuation_date, dict):
                # 如果是字典，尝试从中提取日期
                valuation_date = valuation_date.get("report_date", valuation_date)
                if isinstance(valuation_date, str):
                    from datetime import datetime
                    valuation_date = datetime.strptime(valuation_date, "%Y-%m-%d").date()

            ri_result = await self._calculate_ri_valuation(
                company=company,
                base_financials=base_financials,
                valuation_date=valuation_date,
                base_report_date=report_date,
                cost_of_equity=cost_of_equity,
                growth_rate=growth_rate,
                terminal_growth_rate=terminal_growth_rate,
                projection_years=projection_years,
                payout_ratio=payout_ratio,
            )

            return ri_result

        except Exception as e:
            self.logger.error(f"剩余收益估值失败: {stock_code}, 错误: {str(e)}")
            return {"error": f"剩余收益估值失败: {str(e)}"}

    async def _calculate_ri_valuation(
        self,
        company: Company,
        base_financials: Dict[str, Decimal],
        valuation_date: date,
        base_report_date: date,
        cost_of_equity: Decimal,
        growth_rate: Decimal,
        terminal_growth_rate: Decimal,
        projection_years: int,
        payout_ratio: Decimal,
    ) -> Dict[str, Any]:
        """执行完整的剩余收益估值计算"""

        # 1. 计算当前每股数据
        net_income = base_financials['net_income']
        shareholders_equity = base_financials['shareholders_equity']
        shares_outstanding = base_financials['shares_outstanding']

        # 计算每股收益和每股净资产
        current_eps = net_income / shares_outstanding if shares_outstanding > 0 else Decimal('0')
        current_bps = shareholders_equity / shares_outstanding if shares_outstanding > 0 else Decimal('0')
        current_dps = current_eps * payout_ratio

        # 计算当前ROE
        current_roe = current_eps / current_bps if current_bps > 0 else Decimal('0')

        # 2. 预测每股收益、每股股利和每股净资产
        projected_data = self._project_per_share_data(
            current_eps=current_eps,
            current_bps=current_bps,
            payout_ratio=payout_ratio,
            growth_rate=growth_rate,
            years=projection_years,
        )

        projected_eps = projected_data['eps']
        projected_dps = projected_data['dps']
        projected_bps = projected_data['bps']

        # 3. 计算预测ROE和剩余收益
        projected_roe_and_ri = self._calculate_projected_roe_and_ri(
            projected_eps=projected_eps,
            projected_dps=projected_dps,
            projected_bps=projected_bps,
            cost_of_equity=cost_of_equity,
        )

        projected_roe = projected_roe_and_ri['roe']
        projected_ri = projected_roe_and_ri['ri']

        # 4. 计算每股终值
        terminal_value_per_share = self._calculate_terminal_value_per_share(
            last_ri=projected_ri[-1],
            terminal_growth_rate=terminal_growth_rate,
            cost_of_equity=cost_of_equity,
        )

        # 5. 计算现值
        pv_projected_ri = self._calculate_pv_projected_ri(
            projected_ri=projected_ri,
            cost_of_equity=cost_of_equity,
        )
        pv_terminal_value = self._calculate_pv_terminal_value(
            terminal_value=terminal_value_per_share,
            cost_of_equity=cost_of_equity,
            years=projection_years,
        )

        # 6. 计算每股内在价值（基准）
        # 内在价值 = 当前每股净资产 + 预测期剩余收益现值 + 终值现值
        intrinsic_value_per_share = current_bps + pv_projected_ri + pv_terminal_value

        # 6.5 分析RE趋势
        re_trend = self._analyze_re_trend(projected_ri)

        # 6.6 计算三种情景的估值（基于RE趋势），并为每个情景生成不同的预测记录
        scenarios = {
            'conservative': {
                'valuation': None,
                'upside_downside': None,
                'rating': None,
                're_trend': re_trend,
                'terminal_assumption': 'RE_N+1 = 0',
                'projected_ri': None  # 保守情景的RE预测
            },
            'base': {
                'valuation': None,
                'upside_downside': None,
                'rating': None,
                're_trend': re_trend,
                'terminal_assumption': 'RE_N+1 = RE_N',
                'projected_ri': None  # 基准情景的RE预测
            },
            'optimistic': {
                'valuation': None,
                'upside_downside': None,
                'rating': None,
                're_trend': re_trend,
                'terminal_assumption': 'RE_N+1 = RE_N × (1+g)',
                'projected_ri': None  # 乐观情景的RE预测
            }
        }

        # 保守情景：RE递减，第N年RE接近0
        # 调整增长率，使RE在第N年接近0
        conservative_growth_rate = self._calculate_scenario_growth_rate(
            current_eps=current_eps,
            current_bps=current_bps,
            payout_ratio=payout_ratio,
            cost_of_equity=cost_of_equity,
            projection_years=projection_years,
            target_re_at_end=Decimal('0')  # 目标：第N年RE=0
        )
        conservative_data = self._project_per_share_data(
            current_eps=current_eps,
            current_bps=current_bps,
            payout_ratio=payout_ratio,
            growth_rate=conservative_growth_rate,
            years=projection_years,
        )
        conservative_ri = self._calculate_projected_roe_and_ri(
            projected_eps=conservative_data['eps'],
            projected_dps=conservative_data['dps'],
            projected_bps=conservative_data['bps'],
            cost_of_equity=cost_of_equity,
        )['ri']
        scenarios['conservative']['projected_ri'] = [float(ri) for ri in conservative_ri]

        # 基准情景：RE稳定，第N年RE保持常数（使用原始增长率和参数）
        scenarios['base']['projected_ri'] = [float(ri) for ri in projected_ri]

        # 乐观情景：RE递增，第N年RE继续增长
        # 调整增长率，使RE在第N年比初始RE增长
        initial_re = projected_ri[0]
        target_re_at_end = initial_re * (Decimal('1') + growth_rate)  # 目标：第N年RE增长
        optimistic_growth_rate = self._calculate_scenario_growth_rate(
            current_eps=current_eps,
            current_bps=current_bps,
            payout_ratio=payout_ratio,
            cost_of_equity=cost_of_equity,
            projection_years=projection_years,
            target_re_at_end=target_re_at_end
        )
        optimistic_data = self._project_per_share_data(
            current_eps=current_eps,
            current_bps=current_bps,
            payout_ratio=payout_ratio,
            growth_rate=optimistic_growth_rate,
            years=projection_years,
        )
        optimistic_ri = self._calculate_projected_roe_and_ri(
            projected_eps=optimistic_data['eps'],
            projected_dps=optimistic_data['dps'],
            projected_bps=optimistic_data['bps'],
            cost_of_equity=cost_of_equity,
        )['ri']
        scenarios['optimistic']['projected_ri'] = [float(ri) for ri in optimistic_ri]

        # 计算保守情景估值（无终值）
        pv_projected_ri_conservative = self._calculate_pv_projected_ri(
            projected_ri=conservative_ri,
            cost_of_equity=cost_of_equity,
        )
        valuation_conservative = current_bps + pv_projected_ri_conservative

        # 计算基准情景估值（有终值）
        pv_terminal_base = self._calculate_terminal_value(
            terminal_re=projected_ri[-1],
            cost_of_equity=cost_of_equity,
            projection_years=projection_years,
            terminal_growth_rate=terminal_growth_rate
        )
        valuation_base = current_bps + pv_projected_ri + pv_terminal_base

        # 计算乐观情景估值（有增长终值）
        pv_terminal_optimistic = self._calculate_terminal_value(
            terminal_re=optimistic_ri[-1],
            cost_of_equity=cost_of_equity,
            projection_years=projection_years,
            terminal_growth_rate=terminal_growth_rate
        )
        valuation_optimistic = current_bps + self._calculate_pv_projected_ri(
            projected_ri=optimistic_ri,
            cost_of_equity=cost_of_equity,
        ) + pv_terminal_optimistic

        # 设置情景估值
        scenarios['conservative']['valuation'] = float(valuation_conservative)
        scenarios['base']['valuation'] = float(valuation_base)
        scenarios['optimistic']['valuation'] = float(valuation_optimistic)

        # 7. 计算股权价值
        equity_value = intrinsic_value_per_share * shares_outstanding

        # 8. 计算上涨下跌空间
        current_price = company.current_price or Decimal('0')
        upside_downside = None
        if current_price > 0:
            upside_downside = (
                ((intrinsic_value_per_share - current_price) / current_price * Decimal('100'))
                .quantize(Decimal('0.01'))
            )

        # 8.5 为每种情景计算涨跌幅和评级
        if current_price > 0:
            for scenario_name, scenario_data in scenarios.items():
                scenario_valuation = Decimal(str(scenario_data['valuation']))
                scenario_upside_downside = (
                    ((scenario_valuation - current_price) / current_price * Decimal('100'))
                    .quantize(Decimal('0.01'))
                )
                scenario_data['upside_downside'] = float(scenario_upside_downside)
                scenario_data['rating'] = self._generate_investment_rating(scenario_upside_downside)

        # 9. 生成投资建议
        investment_rating = self._generate_investment_rating(upside_downside)

        # 10. 构建计算详情
        calculation_detail = {
            'current_eps': float(current_eps),
            'current_dps': float(current_dps),
            'current_bps': float(current_bps),
            'current_roe': float(current_roe),
            'dividend_payout_ratio': float(payout_ratio),
            'projected_eps': [float(eps) for eps in projected_eps],
            'projected_dps': [float(dps) for dps in projected_dps],
            'projected_bps': [float(bps) for bps in projected_bps],
            'projected_roe': [float(roe) for roe in projected_roe],
            'projected_ri': [float(ri) for ri in projected_ri],
            'pv_projected_ri_detail': [
                float(ri / (1 + cost_of_equity) ** (i + 1))
                for i, ri in enumerate(projected_ri)
            ],
            'terminal_ri': float(projected_ri[-1] * (1 + terminal_growth_rate)),
            'discount_factors': [
                float(1 / (1 + cost_of_equity) ** (i + 1))
                for i in range(projection_years + 1)
            ]
        }

        assumptions = {
            'cost_of_equity': float(cost_of_equity),
            'growth_rate': float(growth_rate),
            'terminal_growth_rate': float(terminal_growth_rate),
            'projection_years': projection_years,
            'payout_ratio': float(payout_ratio),
            'shares_outstanding': float(shares_outstanding),
        }

        return {
            "company": self._company_to_dict(company),
            "method": "Residual Income (RI)",
            "valuation_date": valuation_date.isoformat(),
            "base_report_date": base_report_date.isoformat(),
            "parameters": assumptions,
            "inputs": {
                "net_income": float(net_income),
                "shareholders_equity": float(shareholders_equity),
                "shares_outstanding": float(shares_outstanding),
                "current_eps": float(current_eps),
                "current_bps": float(current_bps),
                "current_roe": float(current_roe),
            },
            "valuation": {
                "base_book_value_per_share": float(current_bps),
                "pv_forecast_ri": float(pv_projected_ri),
                "terminal_value_per_share": float(terminal_value_per_share),
                "pv_terminal_value": float(pv_terminal_value),
                "intrinsic_value_per_share": float(intrinsic_value_per_share),
                "equity_value": float(equity_value),
                "calculation_detail": calculation_detail,
                "scenarios": scenarios,
                "re_trend": re_trend,  # 添加RE趋势信息
            },
            "current_price": float(current_price),
            "upside_downside": float(upside_downside) if upside_downside is not None else None,
            "investment_rating": investment_rating,
            "margin_of_safety": self._calculate_margin_of_safety(
                float(intrinsic_value_per_share), float(current_price)
            ),
        }

    def _project_per_share_data(
        self,
        current_eps: Decimal,
        current_bps: Decimal,
        payout_ratio: Decimal,
        growth_rate: Decimal,
        years: int,
    ) -> Dict[str, List[Decimal]]:
        """预测每股收益、每股股利和每股净资产"""
        projected_eps = []
        projected_dps = []
        projected_bps = []

        # 初始状态
        prev_eps = current_eps
        bps = current_bps

        for year in range(1, years + 1):
            # 预测每股收益（按增长率增长）
            eps = prev_eps * (1 + growth_rate)
            projected_eps.append(eps)

            # 预测每股股利（假设股利支付率保持不变）
            dps = eps * payout_ratio
            projected_dps.append(dps)

            # 预测每股净资产
            # 每股净资产 = 期初每股净资产 + 每股收益 - 每股股利
            bps = bps + eps - dps
            projected_bps.append(bps)

            # 更新状态
            prev_eps = eps

        return {
            'eps': projected_eps,
            'dps': projected_dps,
            'bps': projected_bps,
        }

    def _calculate_projected_roe_and_ri(
        self,
        projected_eps: List[Decimal],
        projected_dps: List[Decimal],
        projected_bps: List[Decimal],
        cost_of_equity: Decimal,
    ) -> Dict[str, List[Decimal]]:
        """计算预测ROE和剩余收益"""
        projected_roe = []
        projected_ri = []

        for i in range(len(projected_eps)):
            # 使用期初每股净资产计算ROE
            if i == 0:
                # 第一年使用当前每股净资产作为期初
                beginning_bps = projected_bps[0] - projected_eps[0] + projected_dps[0]
            else:
                beginning_bps = projected_bps[i - 1]

            # 计算ROE
            roe = projected_eps[i] / beginning_bps if beginning_bps > 0 else Decimal('0')
            projected_roe.append(roe)

            # 计算剩余收益
            # 剩余收益 = 每股收益 - 股权成本 × 期初每股净资产
            ri = projected_eps[i] - cost_of_equity * beginning_bps
            projected_ri.append(ri)

        return {
            'roe': projected_roe,
            'ri': projected_ri,
        }

    def _calculate_terminal_value_per_share(
        self,
        last_ri: Decimal,
        terminal_growth_rate: Decimal,
        cost_of_equity: Decimal,
    ) -> Decimal:
        """计算每股终值"""
        terminal_ri = last_ri * (1 + terminal_growth_rate)
        denominator = cost_of_equity - terminal_growth_rate

        # 防止除零或负分母
        if denominator <= Decimal('0.001'):
            denominator = Decimal('0.001')

        terminal_value = terminal_ri / denominator
        return terminal_value

    def _calculate_pv_projected_ri(
        self,
        projected_ri: List[Decimal],
        cost_of_equity: Decimal,
    ) -> Decimal:
        """计算预测期剩余收益现值"""
        pv_total = Decimal('0')
        for i, ri in enumerate(projected_ri):
            pv = ri / ((1 + cost_of_equity) ** (i + 1))
            pv_total += pv
        return pv_total

    def _calculate_pv_terminal_value(
        self,
        terminal_value: Decimal,
        cost_of_equity: Decimal,
        years: int,
    ) -> Decimal:
        """计算终值现值"""
        return terminal_value / ((1 + cost_of_equity) ** years)

    async def _get_company(self, stock_code: str) -> Optional[Company]:
        """获取公司信息"""
        from sqlalchemy.orm import selectinload
        result = await self.session.execute(
            select(Company)
            .options(selectinload(Company.industry))
            .where(Company.stock_code == stock_code)
        )
        return result.scalars().first()

    async def _get_latest_report_info(self, stock_code: str) -> Optional[Dict]:
        """获取最近一年的年报日期（优先 annual）"""
        stmt = (
            select(FinancialData.report_date)
            .where(
                FinancialData.company_code == stock_code,
                FinancialData.report_type == ReportType.IS,
                FinancialData.report_period == ReportPeriod.ANNUAL,
            )
            .order_by(FinancialData.report_date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        date_val = result.scalar()
        if date_val:
            return {"report_date": date_val}

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
        date_val = result.scalar()
        if date_val:
            return {"report_date": date_val}
        return None

    async def _get_base_financials(
        self,
        stock_code: str,
        base_year: int,
    ) -> Optional[Dict[str, Decimal]]:
        """获取基准财务数据"""
        try:
            year_start, next_year_start = calendar_year_bounds(base_year)
            financial_data = {}

            # 获取所有需要的财务数据
            for field, codes in self.SUBJECT_CODES.items():
                # 根据科目代码前缀确定报告类型
                prefix = codes[0][:2]
                report_type_mapping = {
                    'IS': ReportType.IS,
                    'BS': ReportType.BS,
                    'CF': ReportType.CF
                }
                report_type = report_type_mapping.get(prefix, ReportType.IS)

                # 查询该年度的财务数据（优先年报）
                for code in codes:
                    value = None
                    for prefer_annual in (True, False):
                        conditions = [
                            FinancialData.company_code == stock_code,
                            FinancialData.subject_code == code,
                            FinancialData.report_date >= year_start,
                            FinancialData.report_date < next_year_start,
                            FinancialData.report_type == report_type,
                        ]
                        if prefer_annual:
                            conditions.append(
                                FinancialData.report_period == ReportPeriod.ANNUAL
                            )
                        stmt = (
                            select(FinancialData.value_decimal)
                            .where(*conditions)
                            .order_by(FinancialData.report_date.desc())
                            .limit(1)
                        )
                        result = await self.session.execute(stmt)
                        value = result.scalar()
                        if value is not None:
                            break

                    if value is not None:
                        financial_data[field] = value
                        break  # 找到第一个有效数据就退出

                # 如果没有找到数据，设置默认值为0
                if field not in financial_data:
                    financial_data[field] = Decimal('0')

            # 获取流通股数
            shares_outstanding = financial_data.get('shares_outstanding', Decimal('0'))
            if shares_outstanding == Decimal('0'):
                self.logger.warning(f"缺少总股本数据: {stock_code}，EPS计算将不准确")

            # 构建返回数据
            result = {
                'revenue': financial_data.get('revenue', Decimal('0')),
                'net_income': financial_data.get('net_income', Decimal('0')),
                'total_assets': financial_data.get('total_assets', Decimal('0')),
                'total_liabilities': financial_data.get('total_liabilities', Decimal('0')),
                'shareholders_equity': financial_data.get('shareholders_equity', Decimal('0')),
                'shares_outstanding': shares_outstanding,
            }

            self.logger.info(f"获取财务数据成功 - {stock_code}: EPS={result['net_income']/shares_outstanding if shares_outstanding > 0 else 0}")
            return result

        except Exception as e:
            self.logger.error(f"获取基准财务数据失败: {stock_code}, 错误: {str(e)}")
            return None

    def _generate_investment_rating(self, upside_downside: Optional[Decimal]) -> str:
        """生成投资建议（基于安全边际）"""
        if upside_downside is None:
            return 'HOLD'

        if upside_downside >= 30:
            return 'STRONG_BUY'
        elif upside_downside >= 15:
            return 'BUY'
        elif upside_downside >= -15:
            return 'HOLD'
        elif upside_downside >= -30:
            return 'REDUCE'
        else:
            return 'SELL'

    def _calculate_margin_of_safety(
        self,
        intrinsic: float,
        price: float,
    ) -> Dict[str, Any]:
        """计算安全边际"""
        if price <= 0:
            return {
                "margin_percent": 0.0,
                "diff": 0.0,
                "status": "unknown",
                "recommendation": "无法计算安全边际 (当前价格无效)"
            }

        margin = (intrinsic - price) / intrinsic

        if margin > 0.3:
            status = "undervalued"
            recommendation = "具有较高安全边际，可考虑买入"
        elif margin > 0.1:
            status = "fairly_valued"
            recommendation = "估值合理，可持有观望"
        else:
            status = "overvalued"
            recommendation = "当前价格较高，注意风险"

        return {
            "margin_percent": round(margin * 100, 2),
            "diff": round(intrinsic - price, 2),
            "status": status,
            "recommendation": recommendation
        }

    def _analyze_re_trend(self, re_sequence: List[Decimal]) -> str:
        """
        分析剩余收益趋势

        Args:
            re_sequence: RE序列 [RE₁, RE₂, ..., RE_N]

        Returns:
            'decreasing' | 'stable' | 'increasing'
        """
        if len(re_sequence) < 2:
            return 'stable'

        # 计算趋势斜率
        n = len(re_sequence)
        x_values = list(range(1, n + 1))

        # 简单线性回归计算斜率
        sum_x = sum(x_values)
        sum_y = sum(re_sequence)
        sum_xy = sum(x * y for x, y in zip(x_values, re_sequence))
        sum_x2 = sum(x ** 2 for x in x_values)

        # 避免除零
        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return 'stable'

        slope = (n * sum_xy - sum_x * sum_y) / denominator

        # 计算平均RE
        avg_re = sum_y / n if sum_y != 0 else Decimal('0')

        # 判断趋势（阈值：平均RE的10%，最小为0.01）
        if avg_re != 0:
            threshold = max(avg_re * Decimal('0.10'), Decimal('0.01'))
        else:
            threshold = Decimal('0.01')

        if slope < -threshold:
            return 'decreasing'
        elif abs(slope) <= threshold:
            return 'stable'
        else:
            return 'increasing'

    def _calculate_terminal_value(
        self,
        terminal_re: Decimal,
        cost_of_equity: Decimal,
        projection_years: int,
        terminal_growth_rate: Decimal,
    ) -> Decimal:
        """
        计算终值的现值

        Args:
            terminal_re: 第N年的剩余收益
            cost_of_equity: 要求回报率
            projection_years: 预测年数
            terminal_growth_rate: 永续增长率

        Returns:
            终值的现值
        """
        r = cost_of_equity
        g = terminal_growth_rate
        n = projection_years

        # 防止负值或无限大
        if r <= g:
            return Decimal('0')

        # 永续增长模型：TV = RE_N × (1+g) / (r-g)
        terminal_value = terminal_re * (Decimal('1') + g) / (r - g)

        # 折现到当前时点：PV = TV / (1+r)^N
        discount_factor = (Decimal('1') + r) ** n
        pv_terminal_value = terminal_value / discount_factor

        return pv_terminal_value

    def _calculate_scenario_growth_rate(
        self,
        current_eps: Decimal,
        current_bps: Decimal,
        payout_ratio: Decimal,
        cost_of_equity: Decimal,
        projection_years: int,
        target_re_at_end: Decimal,
    ) -> Decimal:
        """
        计算情景所需增长率，使第N年的RE达到目标值

        Args:
            current_eps: 当前每股收益
            current_bps: 当前每股净资产
            payout_ratio: 股利支付率
            cost_of_equity: 要求回报率
            projection_years: 预测年数
            target_re_at_end: 第N年目标RE

        Returns:
            所需增长率（如目标不可达则返回边界值）
        """
        if current_bps <= 0 or current_eps <= 0:
            self.logger.warning("bps or eps <= 0, 无法计算增长率")
            return Decimal('0')

        # 先检查目标是否在可达范围内
        min_data = self._project_per_share_data(
            current_eps, current_bps, payout_ratio, Decimal('-0.5'), projection_years
        )
        min_re = self._calculate_projected_roe_and_ri(
            projected_eps=min_data['eps'],
            projected_dps=min_data['dps'],
            projected_bps=min_data['bps'],
            cost_of_equity=cost_of_equity,
        )['ri'][-1]

        max_data = self._project_per_share_data(
            current_eps, current_bps, payout_ratio, Decimal('1.0'), projection_years
        )
        max_re = self._calculate_projected_roe_and_ri(
            projected_eps=max_data['eps'],
            projected_dps=max_data['dps'],
            projected_bps=max_data['bps'],
            cost_of_equity=cost_of_equity,
        )['ri'][-1]

        # 如果目标超出范围，返回最近的边界增长率
        if target_re_at_end < min_re:
            self.logger.warning(
                f"目标RE {target_re_at_end} 低于可达最小值 {min_re}，"
                f"返回 -50% 增长率"
            )
            return Decimal('-0.5')
        if target_re_at_end > max_re:
            self.logger.warning(
                f"目标RE {target_re_at_end} 高于可达最大值 {max_re}，"
                f"返回 100% 增长率"
            )
            return Decimal('1.0')

        # 使用二分法寻找合适的增长率
        low = Decimal('-0.5')  # -50%
        high = Decimal('1.0')   # 100%
        epsilon = Decimal('0.0001')  # 精度

        for _ in range(100):  # 最多迭代100次
            mid = (low + high) / 2

            # 使用当前增长率预测
            projected_data = self._project_per_share_data(
                current_eps=current_eps,
                current_bps=current_bps,
                payout_ratio=payout_ratio,
                growth_rate=mid,
                years=projection_years,
            )

            projected_ri = self._calculate_projected_roe_and_ri(
                projected_eps=projected_data['eps'],
                projected_dps=projected_data['dps'],
                projected_bps=projected_data['bps'],
                cost_of_equity=cost_of_equity,
            )['ri']

            final_re = projected_ri[-1]

            # 比较与目标的差距
            if abs(final_re - target_re_at_end) < epsilon:
                return mid
            elif final_re < target_re_at_end:
                low = mid
            else:
                high = mid

        # 100次迭代后未收敛，返回当前最接近的值并警告
        converged_rate = (low + high) / 2
        converged_data = self._project_per_share_data(
            current_eps, current_bps, payout_ratio, converged_rate, projection_years
        )
        converged_re = self._calculate_projected_roe_and_ri(
            projected_eps=converged_data['eps'],
            projected_dps=converged_data['dps'],
            projected_bps=converged_data['bps'],
            cost_of_equity=cost_of_equity,
        )['ri'][-1]
        if abs(converged_re - target_re_at_end) > epsilon * 100:
            self.logger.warning(
                f"二分搜索未在100次迭代内收敛，"
                f"目标RE={target_re_at_end}, 实际RE={converged_re}"
            )
        return converged_rate

    def _company_to_dict(self, company: Company) -> Dict[str, Any]:
        """将公司对象转换为字典"""
        return {
            "stock_code": company.stock_code,
            "stock_name": company.stock_name,
            "company_name": company.company_name,
            "industry": company.industry.name if company.industry else None,
        }
