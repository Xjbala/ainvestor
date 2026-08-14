# -*- coding: utf-8 -*-
"""
DCF（现金流折现）估值服务

使用自由现金流折现模型估算企业内在价值。

核心公式：
企业价值 = 预测期FCF现值 + 终值现值
股权价值 = 企业价值 - 净债务
每股内在价值 = 股权价值 / 总股本
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


class DCFValuationService:
    """
    DCF 估值服务

    采用两阶段增长模型：
    1. 高增长阶段（通常5年）
    2. 永续增长阶段

    特性：
    - 完整的财务数据获取和验证
    - 详细的中间计算步骤记录
    - 参数假设透明化
    - 自动投资评级生成
    """

    # 默认参数
    DEFAULT_PARAMS = {
        "growth_rate": 0.15,           # 预测期增长率
        "terminal_growth_rate": 0.03,  # 永续增长率
        "discount_rate": 0.10,         # 折现率（WACC）
        "tax_rate": 0.25,              # 企业所得税率
        "projection_years": 5,         # 预测年数
    }

    # 财务科目代码映射
    SUBJECT_CODES = {
        # 利润表科目
        'revenue': ['ISI001'],              # 营业收入
        'operating_income': ['ISF016'],     # 营业利润
        'net_income': ['ISF021'],           # 净利润
        'depreciation_amortization': ['ISF028'],  # 资产减值损失（近似折旧摊销代理）

        # 资产负债表科目
        'total_assets': ['BSA121'],         # 资产总计
        'total_liabilities': ['BSL112'],    # 负债合计
        'shareholders_equity': ['BSE010'],  # 归属于母公司所有者权益合计
        'shares_outstanding': ['BSE001'],   # 实收资本（或股本）

        # 现金流量表科目
        'operating_cash_flow': ['CFO020'],  # 经营活动产生的现金流量净额
        'capital_expenditure': ['CFIV007'], # 购建固定资产、无形资产和其他长期资产支付的现金

        # 债务科目
        'short_term_debt': ['BSL001', 'BSL002', 'BSL003'],  # 短期借款、向中央银行借款、拆入资金
        'long_term_debt': ['BSL102', 'BSL103'],              # 长期借款、应付债券
        'cash': ['BSA001', 'BSA002', 'BSA003'],              # 货币资金、结算备付金、拆出资金

        # === 新增科目（用于新FCF公式）===
        # 利润表科目
        'tax_expense': ['ISF020'],                          # 所得税费用

        # 资产负债表科目 - 用于计算营运资本变化
        'inventory': ['BSA015'],                            # 存货
        'accounts_receivable': ['BSA007'],                  # 应收账款
        'notes_receivable': ['BSA006'],                    # 应收票据
        'advances_to_suppliers': ['BSA009'],                # 预付款项（预付账款）
        'other_receivables': ['BSA013'],                    # 其他应收款
        'accounts_payable': ['BSL007'],                      # 应付账款
        'advances_from_customers': ['BSL008', 'BSL009'],    # 预收款项 + 合同负债
        'notes_payable': ['BSL006'],                        # 应付票据
        'wages_payable': ['BSL014'],                        # 应付职工薪酬（包含福利费）
        'taxes_payable': ['BSL015'],                        # 应交税费
        'other_payables': ['BSL016'],                       # 其他应付款

        # 现金流量表科目
        'subsidiary_investment_cash': ['CFIV009'],          # 取得子公司支付的现金净额
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
        执行 DCF 估值

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
            user_params = params or {}

            # 自动 WACC（用户未显式传 discount_rate 时）
            wacc_breakdown = None
            try:
                from .wacc import WACCService
                wacc_svc = WACCService(self.session)
                wacc_breakdown = await wacc_svc.calculate(stock_code)
                if "discount_rate" not in user_params and "wacc" in wacc_breakdown:
                    calc_params["discount_rate"] = wacc_breakdown["wacc"]
                if "tax_rate" not in user_params and "tax_rate" in wacc_breakdown:
                    calc_params["tax_rate"] = wacc_breakdown["tax_rate"]
            except Exception as e:
                self.logger.warning(f"WACC auto-calc failed for {stock_code}: {e}")

            growth_rate = Decimal(str(calc_params["growth_rate"]))
            terminal_growth_rate = Decimal(str(calc_params["terminal_growth_rate"]))
            discount_rate = Decimal(str(calc_params["discount_rate"]))
            tax_rate = Decimal(str(calc_params["tax_rate"]))
            projection_years = int(calc_params["projection_years"])

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

            # 附加 WACC / 行业退出倍数
            if wacc_breakdown:
                base_financials["wacc_breakdown"] = wacc_breakdown
                base_financials["exit_ev_ebitda"] = Decimal(
                    str(wacc_breakdown.get("exit_ev_ebitda") or 12.0)
                )
                base_financials["wacc_band"] = (wacc_breakdown.get("sanity") or {}).get("band")

            # 4. 执行 DCF 计算
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

            dcf_result = await self._calculate_dcf_valuation(
                company=company,
                base_financials=base_financials,
                valuation_date=valuation_date,
                base_report_date=report_date,
                growth_rate=growth_rate,
                terminal_growth_rate=terminal_growth_rate,
                discount_rate=discount_rate,
                tax_rate=tax_rate,
                projection_years=projection_years,
            )

            return dcf_result

        except Exception as e:
            self.logger.error(f"DCF估值失败: {stock_code}, 错误: {str(e)}")
            return {"error": f"DCF估值失败: {str(e)}"}

    async def _calculate_dcf_valuation(
        self,
        company: Company,
        base_financials: Dict[str, Decimal],
        valuation_date: date,
        base_report_date: date,
        growth_rate: Decimal,
        terminal_growth_rate: Decimal,
        discount_rate: Decimal,
        tax_rate: Decimal,
        projection_years: int,
    ) -> Dict[str, Any]:
        """执行完整的 DCF 估值计算"""

        # 1. 获取基准自由现金流
        base_fcf = base_financials['free_cash_flow']

        # 验证 FCF 为正
        if base_fcf <= Decimal('0'):
            return {
                "company": self._company_to_dict(company),
                "error": f"基准自由现金流为负或零 ({base_fcf})，DCF模型不适用",
                "inputs": {
                    "operating_cash_flow": float(base_financials.get('operating_cash_flow', 0)),
                    "capital_expenditure": float(base_financials.get('capital_expenditure', 0)),
                    "base_fcf": float(base_fcf),
                }
            }

        # 2. 计算预测期自由现金流
        projected_fcf = self._calculate_projected_fcf(
            base_fcf, growth_rate, projection_years
        )

        # 3. 计算终值
        terminal_value = self._calculate_terminal_value(
            projected_fcf[-1], terminal_growth_rate, discount_rate
        )

        # 4. 计算现值
        pv_projected_fcf = self._calculate_pv_projected_fcf(projected_fcf, discount_rate)
        pv_terminal_value = self._calculate_pv_terminal_value(
            terminal_value, discount_rate, projection_years
        )

        # 4b. 双终值：Gordon + Exit Multiple（取中点）
        terminal_methods = self._dual_terminal_value(
            last_fcf=projected_fcf[-1],
            terminal_growth_rate=terminal_growth_rate,
            discount_rate=discount_rate,
            ebitda_proxy=base_financials.get('operating_income', Decimal('0')),
            exit_multiple=base_financials.get('exit_ev_ebitda'),
            growth_rate=growth_rate,
            projection_years=projection_years,
        )
        if terminal_methods.get("tv_blended") is not None:
            terminal_value = Decimal(str(terminal_methods["tv_blended"]))
            pv_terminal_value = self._calculate_pv_terminal_value(
                terminal_value, discount_rate, projection_years
            )

        # 5. 计算企业价值和股权价值
        enterprise_value = pv_projected_fcf + pv_terminal_value
        net_debt = base_financials.get('net_debt', Decimal('0'))
        equity_value = enterprise_value - net_debt

        # 6. 计算每股内在价值
        shares_outstanding = base_financials.get('shares_outstanding')
        if shares_outstanding is None or shares_outstanding <= 0:
            return {
                "company": self._company_to_dict(company),
                "error": "缺少总股本数据，无法计算每股内在价值",
                "inputs": {
                    "equity_value": float(equity_value),
                    "enterprise_value": float(enterprise_value),
                    "net_debt": float(net_debt),
                }
            }
        intrinsic_value_per_share = equity_value / shares_outstanding

        # 7. 计算上涨下跌空间
        current_price = company.current_price or Decimal('0')
        upside_downside = None
        if current_price > 0:
            upside_downside = (
                ((intrinsic_value_per_share - current_price) / current_price * Decimal('100'))
                .quantize(Decimal('0.01'))
            )

        # 8. 生成投资建议
        investment_rating = self._generate_investment_rating(upside_downside)

        # 9. 分析FCF趋势
        fcf_trend = self._analyze_fcf_trend(projected_fcf)

        # 9.5 计算三种情景的估值（基于FCF趋势）
        # 三个情景共享相同的 projected_fcf 和 pv_projected_fcf，
        # 唯一差异是终值增长率（影响 terminal_value 和 pv_terminal_value）
        pv_projected_fcf_cached = pv_projected_fcf  # 缓存：投影期现值（三个情景相同）

        scenario_configs = [
            ('conservative', Decimal('0.015'), '低永续增长率 (1.5%)'),
            ('base', terminal_growth_rate, '基准永续增长率 (3%)'),
            ('optimistic', Decimal('0.045'), '高永续增长率 (4.5%)'),
        ]

        scenarios: Dict[str, Any] = {}
        for name, term_growth, assumption_desc in scenario_configs:
            # 计算该情景的终值和现值
            tv = self._calculate_terminal_value(
                projected_fcf[-1], term_growth, discount_rate
            )
            pv_tv = self._calculate_pv_terminal_value(tv, discount_rate, projection_years)

            # 企业价值 = 投影期现值（缓存）+ 终值现值
            enterprise_val = pv_projected_fcf_cached + pv_tv
            equity_val = enterprise_val - net_debt

            # 每股价值
            per_share_val = equity_val / shares_outstanding if shares_outstanding > 0 else Decimal('0')

            scenarios[name] = {
                'valuation': float(per_share_val),
                'fcf_trend': fcf_trend,
                'terminal_assumption': assumption_desc,
                'projected_fcf': [float(f) for f in projected_fcf],
                'terminal_growth_rate': float(term_growth),
                'terminal_value': float(tv),
                'pv_projected_fcf': float(pv_projected_fcf_cached),
                'pv_terminal_value': float(pv_tv),
                'enterprise_value': float(enterprise_val),
                'equity_value': float(equity_val),
            }

        # 为每种情景计算涨跌幅和评级
        if current_price > 0:
            for scenario_name, scenario_data in scenarios.items():
                scenario_valuation = Decimal(str(scenario_data['valuation']))
                scenario_upside_downside = (
                    ((scenario_valuation - current_price) / current_price * Decimal('100'))
                    .quantize(Decimal('0.01'))
                )
                scenario_data['upside_downside'] = float(scenario_upside_downside)
                scenario_data['rating'] = self._generate_investment_rating(scenario_upside_downside)

        # 10. 构建计算详情
        calculation_detail = {
            'base_fcf': float(base_fcf),
            'projected_fcf': [float(fcf) for fcf in projected_fcf],
            'pv_projected_fcf_detail': [
                float(fcf / (1 + discount_rate) ** (i + 1))
                for i, fcf in enumerate(projected_fcf)
            ],
            'terminal_fcf': float(projected_fcf[-1] * (1 + terminal_growth_rate)),
            'terminal_value': float(terminal_value),
            'discount_factors': [
                float(1 / (1 + discount_rate) ** (i + 1))
                for i in range(projection_years + 1)
            ]
        }

        assumptions = {
            'growth_rate': float(growth_rate),
            'terminal_growth_rate': float(terminal_growth_rate),
            'discount_rate': float(discount_rate),
            'tax_rate': float(tax_rate),
            'projection_years': projection_years,
            'shares_outstanding': float(shares_outstanding),
            'net_debt': float(net_debt)
        }

        # 敏感性矩阵 + 质量 gate
        sensitivity = None
        try:
            from .scenarios import build_sensitivity_grid
            sensitivity = build_sensitivity_grid(
                base_wacc=float(discount_rate),
                base_g=float(terminal_growth_rate),
                last_fcf=float(projected_fcf[-1]),
                pv_projected_fcf=float(pv_projected_fcf),
                net_debt=float(net_debt),
                shares=float(shares_outstanding),
                projection_years=projection_years,
            )
        except Exception as e:
            self.logger.warning(f"sensitivity grid failed: {e}")

        tv_share = float(pv_terminal_value / enterprise_value) if enterprise_value > 0 else None
        gates = self._build_dcf_gates(
            discount_rate=float(discount_rate),
            terminal_growth_rate=float(terminal_growth_rate),
            tv_share=tv_share,
            terminal_methods=terminal_methods,
            wacc_band=base_financials.get("wacc_band"),
        )

        wacc_breakdown = base_financials.get("wacc_breakdown")

        return {
            "company": self._company_to_dict(company),
            "method": "DCF (Discounted Cash Flow)",
            "valuation_date": valuation_date.isoformat(),
            "base_report_date": base_report_date.isoformat(),
            "parameters": assumptions,
            "wacc_breakdown": wacc_breakdown,
            "gates": gates,
            "inputs": {
                "revenue": float(base_financials.get('revenue', 0)),
                "operating_income": float(base_financials.get('operating_income', 0)),
                "net_income": float(base_financials.get('net_income', 0)),
                "operating_cash_flow": float(base_financials.get('operating_cash_flow', 0)),
                "capital_expenditure": float(base_financials.get('capital_expenditure', 0)),
                "base_fcf": float(base_fcf),
                "net_debt": float(net_debt),
                "shares_outstanding": float(shares_outstanding),
            },
            "valuation": {
                "pv_projected_fcf": float(pv_projected_fcf),
                "terminal_value": float(terminal_value),
                "pv_terminal_value": float(pv_terminal_value),
                "enterprise_value": float(enterprise_value),
                "equity_value": float(equity_value),
                "intrinsic_value_per_share": float(intrinsic_value_per_share),
                "calculation_detail": calculation_detail,
                "scenarios": scenarios,
                "fcf_trend": fcf_trend,
                "terminal_methods": terminal_methods,
                "tv_share_of_ev": tv_share,
                "sensitivity": sensitivity,
                "gates": gates,
            },
            "current_price": float(current_price),
            "upside_downside": float(upside_downside) if upside_downside is not None else None,
            "investment_rating": investment_rating,
            "margin_of_safety": self._calculate_margin_of_safety(
                float(intrinsic_value_per_share), float(current_price)
            ),
        }

    def _calculate_projected_fcf(
        self,
        base_fcf: Decimal,
        growth_rate: Decimal,
        years: int,
    ) -> List[Decimal]:
        """计算预测期自由现金流"""
        projected_fcf = []
        for year in range(1, years + 1):
            fcf = base_fcf * ((1 + growth_rate) ** year)
            projected_fcf.append(fcf)
        return projected_fcf

    def _calculate_terminal_value(
        self,
        last_year_fcf: Decimal,
        terminal_growth_rate: Decimal,
        discount_rate: Decimal,
    ) -> Decimal:
        """计算终值"""
        terminal_fcf = last_year_fcf * (1 + terminal_growth_rate)
        denominator = discount_rate - terminal_growth_rate

        # 防止除零或负分母
        if denominator <= Decimal('0.001'):
            denominator = Decimal('0.001')

        terminal_value = terminal_fcf / denominator
        return terminal_value

    def _calculate_pv_projected_fcf(
        self,
        projected_fcf: List[Decimal],
        discount_rate: Decimal,
    ) -> Decimal:
        """计算预测期现金流现值"""
        pv_total = Decimal('0')
        for i, fcf in enumerate(projected_fcf):
            pv = fcf / ((1 + discount_rate) ** (i + 1))
            pv_total += pv
        return pv_total

    def _calculate_pv_terminal_value(
        self,
        terminal_value: Decimal,
        discount_rate: Decimal,
        years: int,
    ) -> Decimal:
        """计算终值现值"""
        return terminal_value / ((1 + discount_rate) ** years)

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
        """获取最近一年的年报日期（优先 annual，避免季报污染基准年）"""
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

        # 回退：任意最近报告期
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

    async def _get_balance_sheet_value(
        self,
        stock_code: str,
        subject_code: str,
        year: int,
    ) -> Optional[Decimal]:
        """获取指定年份的资产负债表值"""
        year_start, next_year_start = calendar_year_bounds(year)
        stmt = (
            select(FinancialData.value_decimal)
            .where(
                FinancialData.company_code == stock_code,
                FinancialData.subject_code == subject_code,
                FinancialData.report_date >= year_start,
                FinancialData.report_date < next_year_start,
                FinancialData.report_type == ReportType.BS
            )
            .order_by(FinancialData.report_date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar()

    async def _get_balance_sheet_changes(
        self,
        stock_code: str,
        base_year: int,
    ) -> Dict[str, Decimal]:
        """
        获取资产负债表科目的期初期末变化量

        返回: {科目名: (期末值 - 期初值)}
        如果只有一年数据，期初值设为0
        """
        # 需要计算变化量的科目
        change_fields = [
            'inventory', 'accounts_receivable', 'notes_receivable',
            'advances_to_suppliers', 'other_receivables', 'prepaid_expenses',
            'accounts_payable', 'advances_from_customers', 'notes_payable',
            'wages_payable', 'taxes_payable', 'other_payables',
            'cash',
        ]

        changes = {}

        for field in change_fields:
            codes = self.SUBJECT_CODES.get(field, [])
            if not codes:
                changes[field] = Decimal('0')
                continue

            # 获取期末值（基准年）
            end_value = Decimal('0')
            for code in codes:
                value = await self._get_balance_sheet_value(stock_code, code, base_year)
                if value is not None:
                    end_value += value

            # 获取期初值（上一年），如果不存在则为0
            prev_year = base_year - 1
            start_value = Decimal('0')
            for code in codes:
                value = await self._get_balance_sheet_value(stock_code, code, prev_year)
                if value is not None:
                    start_value += value

            # 计算变化量 = 期末 - 期初
            changes[field] = end_value - start_value

        return changes

    def _calculate_free_cash_flow_new(
        self,
        base_financials: Dict[str, Decimal],
        balance_sheet_changes: Dict[str, Decimal],
    ) -> Decimal:
        """
        使用标准公式计算自由现金流（FCFF）

        FCF = 净利润 + 折旧与摊销 - 营运资本增加 - 资本支出

        其中：
        - 净利润 = 利润表中"净利润"科目（已扣税，直接使用）
        - 折旧与摊销 = 利润表中"资产减值损失"科目（新准则下含折旧摊销）
        - 营运资本增加 = 经营性流动资产增加 - 经营性流动负债增加
          - 经营性流动资产 = 应收账款 + 应收票据 + 预付款项 + 其他应收款
          - 经营性流动负债 = 应付账款 + 预收款项 + 应付票据 + 应付职工薪酬 + 应交税费 + 其他应付款
        - 资本支出 = 购建固定资产等 + 子公司投资现金
        """
        # 1. 净利润（直接使用利润表中的净利润，已扣税）
        net_income = base_financials.get('net_income', Decimal('0'))

        # 2. 折旧与摊销
        depreciation_amortization = base_financials.get('depreciation_amortization', Decimal('0'))

        # 3. 营运资本增加 = 经营性应收增加 - 经营性应付增加
        # 注意：货币资金变化不计入营运资本变动（属于融资活动）
        # 注意：存货变化不计入（制造业存货波动大，且已在FCF间接法中通过净利润调整）
        receivables_change = (
            balance_sheet_changes.get('accounts_receivable', Decimal('0')) +
            balance_sheet_changes.get('notes_receivable', Decimal('0')) +
            balance_sheet_changes.get('advances_to_suppliers', Decimal('0')) +
            balance_sheet_changes.get('other_receivables', Decimal('0'))
        )

        payables_change = (
            balance_sheet_changes.get('accounts_payable', Decimal('0')) +
            balance_sheet_changes.get('advances_from_customers', Decimal('0')) +
            balance_sheet_changes.get('notes_payable', Decimal('0')) +
            balance_sheet_changes.get('wages_payable', Decimal('0')) +
            balance_sheet_changes.get('taxes_payable', Decimal('0')) +
            balance_sheet_changes.get('other_payables', Decimal('0'))
        )

        # 营运资本增加 = 经营性应收增加 - 经营性应付增加
        working_capital_increase = receivables_change - payables_change

        # 4. 资本支出
        capital_expenditure = base_financials.get('capital_expenditure', Decimal('0'))
        subsidiary_investment = base_financials.get('subsidiary_investment_cash', Decimal('0'))
        total_capital_expenditure = capital_expenditure + subsidiary_investment

        # 5. FCF = 净利润 + 折旧与摊销 - 营运资本增加 - 资本支出
        fcf = (
            net_income +
            depreciation_amortization -
            working_capital_increase -
            total_capital_expenditure
        )

        return fcf

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

                # 查询该年度的财务数据（优先年报 12-31）
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
                        if field in ['short_term_debt', 'long_term_debt', 'cash']:
                            # 累加债务和现金相关科目
                            financial_data[field] = financial_data.get(field, Decimal('0')) + value
                        else:
                            financial_data[field] = value
                            break  # 找到第一个有效数据就退出

                # 如果没有找到数据，设置默认值为0
                if field not in financial_data:
                    financial_data[field] = Decimal('0')

            # 获取资产负债表期初期末变化量（用于新FCF公式）
            balance_sheet_changes = await self._get_balance_sheet_changes(stock_code, base_year)

            # 获取原始现金流数据（用于向后兼容）
            operating_cash_flow = financial_data.get('operating_cash_flow', Decimal('0'))
            capital_expenditure = abs(financial_data.get('capital_expenditure', Decimal('0')))

            # 使用新公式计算自由现金流
            free_cash_flow = self._calculate_free_cash_flow_new(financial_data, balance_sheet_changes)

            # 计算净债务 = 总债务 - 现金
            total_debt = financial_data.get('short_term_debt', Decimal('0')) + \
                        financial_data.get('long_term_debt', Decimal('0'))
            cash = financial_data.get('cash', Decimal('0'))
            net_debt = max(total_debt - cash, Decimal('0'))

            # 构建返回数据
            result = {
                'revenue': financial_data.get('revenue', Decimal('0')),
                'operating_income': financial_data.get('operating_income', Decimal('0')),
                'net_income': financial_data.get('net_income', Decimal('0')),
                'total_assets': financial_data.get('total_assets', Decimal('0')),
                'total_liabilities': financial_data.get('total_liabilities', Decimal('0')),
                'shareholders_equity': financial_data.get('shareholders_equity', Decimal('0')),
                # 原始现金流数据
                'operating_cash_flow': operating_cash_flow,
                'capital_expenditure': capital_expenditure,
                # 新FCF公式相关数据
                'tax_expense': financial_data.get('tax_expense', Decimal('0')),
                'depreciation_amortization': financial_data.get('depreciation_amortization', Decimal('0')),
                'subsidiary_investment_cash': financial_data.get('subsidiary_investment_cash', Decimal('0')),
                # 计算结果
                'free_cash_flow': free_cash_flow,
                'net_debt': net_debt,
                'shares_outstanding': financial_data.get('shares_outstanding', None),
            }

            self.logger.info(f"获取财务数据成功 - {stock_code}: FCF={free_cash_flow}")
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

    def _company_to_dict(self, company: Company) -> Dict[str, Any]:
        """将公司对象转换为字典"""
        return {
            "stock_code": company.stock_code,
            "stock_name": company.stock_name,
            "company_name": company.company_name,
            "industry": company.industry.name if company.industry else None,
        }

    def _dual_terminal_value(
        self,
        last_fcf: Decimal,
        terminal_growth_rate: Decimal,
        discount_rate: Decimal,
        ebitda_proxy: Decimal,
        exit_multiple: Optional[Decimal],
        growth_rate: Decimal,
        projection_years: int,
    ) -> Dict[str, Any]:
        """Gordon + Exit Multiple 双终值，返回中点合成。"""
        gordon = self._calculate_terminal_value(last_fcf, terminal_growth_rate, discount_rate)

        # 用经营利润近似 EBITDA 并外推至第 N 年
        mult = float(exit_multiple) if exit_multiple is not None else 12.0
        ebitda_n = float(ebitda_proxy) * ((1 + float(growth_rate)) ** projection_years)
        if ebitda_n <= 0:
            # 退化：用 FCF 的倍数近似
            ebitda_n = float(last_fcf) * 1.2
        tv_exit = Decimal(str(ebitda_n * mult))

        blended = (gordon + tv_exit) / Decimal("2")
        if gordon > 0:
            divergence = abs(float(tv_exit - gordon)) / float(gordon)
        else:
            divergence = None

        return {
            "tv_gordon": float(gordon),
            "tv_exit_multiple": float(tv_exit),
            "exit_ev_ebitda": mult,
            "ebitda_year_n": ebitda_n,
            "tv_blended": float(blended),
            "divergence_pct": round(divergence * 100, 2) if divergence is not None else None,
            "method": "midpoint(gordon, exit_multiple)",
        }

    def _build_dcf_gates(
        self,
        discount_rate: float,
        terminal_growth_rate: float,
        tv_share: Optional[float],
        terminal_methods: Dict[str, Any],
        wacc_band: Optional[list],
    ) -> List[Dict[str, Any]]:
        gates: List[Dict[str, Any]] = []
        gates.append({
            "name": "wacc_gt_g",
            "ok": discount_rate > terminal_growth_rate + 0.001,
            "message": None if discount_rate > terminal_growth_rate + 0.001
            else f"WACC({discount_rate:.2%}) 未显著高于永续增长率({terminal_growth_rate:.2%})",
        })
        if tv_share is not None:
            ok = 0.45 <= tv_share <= 0.85
            gates.append({
                "name": "tv_share_of_ev",
                "ok": ok,
                "value": round(tv_share, 4),
                "message": None if ok else f"终值占 EV 比例 {tv_share:.0%}，建议检查假设（正常 45%-85%）",
            })
        div = terminal_methods.get("divergence_pct")
        if div is not None:
            ok = div <= 30
            gates.append({
                "name": "dual_terminal_convergence",
                "ok": ok,
                "value": div,
                "message": None if ok else f"Gordon 与 Exit Multiple 终值偏差 {div}%，请交叉检查",
            })
        if wacc_band and len(wacc_band) == 2:
            lo, hi = float(wacc_band[0]), float(wacc_band[1])
            ok = lo <= discount_rate <= hi
            gates.append({
                "name": "wacc_sector_band",
                "ok": ok,
                "message": None if ok else f"WACC {discount_rate:.2%} 超出行业区间 {lo:.0%}-{hi:.0%}",
            })
        return gates

    def _analyze_fcf_trend(self, fcf_sequence: List[Decimal]) -> str:
        """
        分析自由现金流趋势

        Args:
            fcf_sequence: FCF序列 [FCF₁, FCF₂, ..., FCF_N]

        Returns:
            'decreasing' | 'stable' | 'increasing'
        """
        if len(fcf_sequence) < 2:
            return 'stable'

        # 计算趋势斜率
        n = len(fcf_sequence)
        x_values = list(range(1, n + 1))

        # 简单线性回归计算斜率
        sum_x = sum(x_values)
        sum_y = sum(fcf_sequence)
        sum_xy = sum(x * y for x, y in zip(x_values, fcf_sequence))
        sum_x2 = sum(x ** 2 for x in x_values)

        # 避免除零
        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return 'stable'

        slope = (n * sum_xy - sum_x * sum_y) / denominator

        # 计算平均FCF
        avg_fcf = sum_y / n if sum_y != 0 else Decimal('0')

        # 判断趋势（阈值：平均FCF的10%，最小为0.01）
        if avg_fcf != 0:
            threshold = max(avg_fcf * Decimal('0.10'), Decimal('0.01'))
        else:
            threshold = Decimal('0.01')

        if slope < -threshold:
            return 'decreasing'
        elif abs(slope) <= threshold:
            return 'stable'
        else:
            return 'increasing'

    def _calculate_scenario_growth_rate(
        self,
        base_fcf: Decimal,
        projection_years: int,
        target_fcf_at_end: Decimal,
    ) -> Decimal:
        """
        计算情景所需增长率，使第N年的FCF达到目标值

        Args:
            base_fcf: 基准自由现金流
            projection_years: 预测年数
            target_fcf_at_end: 第N年目标FCF

        Returns:
            所需增长率（如目标不可达则返回边界值）
        """
        if base_fcf <= 0:
            self.logger.warning("base_fcf <= 0, 无法计算增长率")
            return Decimal('0')

        # 先检查目标是否在可达范围内
        # 用最低增长率(-50%)计算可达的最小终值
        min_fcf = self._calculate_projected_fcf(base_fcf, Decimal('-0.5'), projection_years)[-1]
        # 用最高增长率(100%)计算可达的最大终值
        max_fcf = self._calculate_projected_fcf(base_fcf, Decimal('1.0'), projection_years)[-1]

        # 如果目标超出范围，返回最近的边界增长率
        if target_fcf_at_end < min_fcf:
            self.logger.warning(
                f"目标FCF {target_fcf_at_end} 低于可达最小值 {min_fcf}，"
                f"返回 -50% 增长率"
            )
            return Decimal('-0.5')
        if target_fcf_at_end > max_fcf:
            self.logger.warning(
                f"目标FCF {target_fcf_at_end} 高于可达最大值 {max_fcf}，"
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
            projected_fcf = self._calculate_projected_fcf(
                base_fcf, mid, projection_years
            )

            final_fcf = projected_fcf[-1]

            # 比较与目标的差距
            if abs(final_fcf - target_fcf_at_end) < epsilon:
                return mid
            elif final_fcf < target_fcf_at_end:
                low = mid
            else:
                high = mid

        # 100次迭代后未收敛，返回当前最接近的值并警告
        converged_rate = (low + high) / 2
        final_at_converged = self._calculate_projected_fcf(
            base_fcf, converged_rate, projection_years
        )[-1]
        if abs(final_at_converged - target_fcf_at_end) > epsilon * 100:
            self.logger.warning(
                f"二分搜索未在100次迭代内收敛，"
                f"目标FCF={target_fcf_at_end}, 实际FCF={final_at_converged}"
            )
        return converged_rate
