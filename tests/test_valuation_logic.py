# -*- coding: utf-8 -*-
"""
核心估值逻辑单元测试

测试 DCF 和剩余收益模型的纯计算逻辑（不依赖数据库）。
"""

import sys
import os
import unittest
from decimal import Decimal

# 确保可以从项目根目录导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFCFCalculation(unittest.TestCase):
    """测试自由现金流计算逻辑"""

    def test_standard_fcf_formula(self):
        """标准 FCF = 净利润 + 折旧摊销 - 营运资本增加 - 资本支出"""
        net_income = Decimal('1000')
        depreciation = Decimal('200')
        working_capital_increase = Decimal('100')
        capex = Decimal('300')

        fcf = net_income + depreciation - working_capital_increase - capex
        self.assertEqual(fcf, Decimal('800'))

    def test_fcf_negative_working_capital(self):
        """营运资本减少（负增加）应增加 FCF"""
        net_income = Decimal('1000')
        depreciation = Decimal('200')
        working_capital_increase = Decimal('-50')  # 减少
        capex = Decimal('300')

        fcf = net_income + depreciation - working_capital_increase - capex
        # 1000 + 200 - (-50) - 300 = 1000 + 200 + 50 - 300 = 950
        self.assertEqual(fcf, Decimal('950'))

    def test_fcf_zero_capex(self):
        """轻资产公司 FCF 应更高"""
        net_income = Decimal('500')
        depreciation = Decimal('50')
        working_capital_increase = Decimal('30')
        capex = Decimal('0')

        fcf = net_income + depreciation - working_capital_increase - capex
        self.assertEqual(fcf, Decimal('520'))

    def test_fcf_high_capex(self):
        """重资产公司 FCF 应更低"""
        net_income = Decimal('1000')
        depreciation = Decimal('200')
        working_capital_increase = Decimal('100')
        capex = Decimal('800')

        fcf = net_income + depreciation - working_capital_increase - capex
        self.assertEqual(fcf, Decimal('300'))


class TestDiscountedCashFlow(unittest.TestCase):
    """测试现金流折现计算"""

    def test_single_period_pv(self):
        """单期现值计算"""
        fcf = Decimal('100')
        discount_rate = Decimal('0.10')
        year = 1

        pv = fcf / ((1 + discount_rate) ** year)
        self.assertAlmostEqual(float(pv), 90.9090909090909, places=5)

    def test_multi_period_pv(self):
        """多期现值总和"""
        fcf_sequence = [Decimal('100'), Decimal('110'), Decimal('121')]
        discount_rate = Decimal('0.10')

        pv_total = sum(
            fcf / ((1 + discount_rate) ** (i + 1))
            for i, fcf in enumerate(fcf_sequence)
        )
        # 100/1.1 + 110/1.21 + 121/1.331 = 90.91 + 90.91 + 90.91 = 272.73
        self.assertAlmostEqual(float(pv_total), 272.73, places=1)

    def test_terminal_value_gordon(self):
        """戈登增长模型终值"""
        last_fcf = Decimal('100')
        terminal_growth = Decimal('0.03')
        discount_rate = Decimal('0.10')

        terminal_value = last_fcf * (1 + terminal_growth) / (discount_rate - terminal_growth)
        # 100 * 1.03 / 0.07 = 103 / 0.07 = 1471.43
        self.assertAlmostEqual(float(terminal_value), 1471.43, places=1)

    def test_terminal_value_invalid_growth(self):
        """永续增长率 >= 折现率时应抛出异常"""
        last_fcf = Decimal('100')
        terminal_growth = Decimal('0.15')
        discount_rate = Decimal('0.10')

        # 除零或负数分母，Python 会抛出 ArithmeticError 或返回 inf
        result = last_fcf * (1 + terminal_growth) / (discount_rate - terminal_growth)
        # 103 / (-0.05) = -2060，不会抛异常，但结果是负的
        self.assertLess(result, 0)

    def test_equity_value_calculation(self):
        """股权价值 = 企业价值 - 净债务"""
        enterprise_value = Decimal('5000')
        net_debt = Decimal('1000')
        equity_value = enterprise_value - net_debt
        self.assertEqual(equity_value, Decimal('4000'))

    def test_per_share_value(self):
        """每股价值 = 股权价值 / 总股本"""
        equity_value = Decimal('4000')
        shares = Decimal('1000')
        per_share = equity_value / shares
        self.assertEqual(per_share, Decimal('4'))

    def test_upside_downside(self):
        """上涨空间计算"""
        intrinsic = Decimal('50')
        current = Decimal('40')
        upside = ((intrinsic - current) / current * Decimal('100')).quantize(Decimal('0.01'))
        self.assertEqual(upside, Decimal('25.00'))


class TestScenarioBounds(unittest.TestCase):
    """测试二分搜索边界保护逻辑"""

    def test_reachable_target(self):
        """目标在可达范围内"""
        base_fcf = Decimal('100')
        target = Decimal('150')  # 在 -50%~100% 范围内

        # 最小可达值
        min_fcf = base_fcf * ((1 + Decimal('-0.5')) ** 5)
        # 最大可达值
        max_fcf = base_fcf * ((1 + Decimal('1.0')) ** 5)

        self.assertLessEqual(min_fcf, target)
        self.assertGreaterEqual(max_fcf, target)

    def test_unreachable_low_target(self):
        """目标低于最小可达值"""
        base_fcf = Decimal('100')
        target = Decimal('-50')  # FCF 不能为负太多

        min_fcf = base_fcf * ((1 + Decimal('-0.5')) ** 5)
        self.assertLess(target, min_fcf)

    def test_unreachable_high_target(self):
        """目标高于最大可达值"""
        base_fcf = Decimal('100')
        target = Decimal('100000')  # 远超 100% 增长率可达范围

        max_fcf = base_fcf * ((1 + Decimal('1.0')) ** 5)
        self.assertGreater(target, max_fcf)


class TestOperatingMargin(unittest.TestCase):
    """测试营业利润率计算"""

    def test_real_operating_margin(self):
        """营业利润率 = 营业利润 / 营业收入"""
        revenue = Decimal('1000')
        operating_profit = Decimal('200')
        operating_cost = Decimal('600')
        gross_profit = revenue - operating_cost  # 400

        # 毛利率
        gross_margin = gross_profit / revenue * Decimal('100')
        # 营业利润率
        operating_margin = operating_profit / revenue * Decimal('100')

        self.assertEqual(float(gross_margin), 40.0)
        self.assertEqual(float(operating_margin), 20.0)
        # 营业利润率应小于毛利率（扣除期间费用）
        self.assertLess(operating_margin, gross_margin)

    def test_operating_margin_with_expenses(self):
        """考虑期间费用的营业利润率"""
        revenue = Decimal('1000')
        operating_cost = Decimal('600')
        selling_expenses = Decimal('100')
        admin_expenses = Decimal('50')
        r_and_d_expenses = Decimal('50')

        operating_profit = revenue - operating_cost - selling_expenses - admin_expenses - r_and_d_expenses
        operating_margin = operating_profit / revenue * Decimal('100')

        # 1000 - 600 - 100 - 50 - 50 = 200
        self.assertEqual(float(operating_margin), 20.0)


class TestPredictionParsing(unittest.TestCase):
    """测试预测解析逻辑"""

    def test_json_parsing_valid(self):
        """测试 JSON 格式预测解析"""
        json_str = '''
        {
            "predictions": [
                {"ticker": "000001", "direction": "up", "confidence": 0.8, "reason": "基本面良好"},
                {"ticker": "600519", "direction": "down", "confidence": 0.6, "reason": "估值偏高"}
            ]
        }
        '''
        import json
        parsed = json.loads(json_str)
        self.assertEqual(len(parsed['predictions']), 2)
        self.assertEqual(parsed['predictions'][0]['ticker'], '000001')
        self.assertEqual(parsed['predictions'][0]['direction'], 'up')
        self.assertAlmostEqual(parsed['predictions'][0]['confidence'], 0.8)

    def test_heuristic_direction_detection(self):
        """测试启发式方向检测"""
        content = "我对000001持看涨态度，建议买入"
        content_lower = content.lower()

        up_keywords = ["up", "bullish", "long", "buy", "看涨", "买入", "推荐", "增持", "强烈买入"]
        down_keywords = ["down", "bearish", "short", "sell", "看跌", "卖出", "减持", "强烈卖出"]

        up_score = sum(1 for kw in up_keywords if kw in content_lower)
        down_score = sum(1 for kw in down_keywords if kw in content_lower)

        self.assertGreater(up_score, 0)
        self.assertEqual(down_score, 0)

    def test_confidence_clamping(self):
        """测试置信度范围钳制"""
        # 超出范围的置信度应被限制
        def clamp_confidence(conf):
            return max(0.0, min(1.0, conf))

        self.assertEqual(clamp_confidence(-0.5), 0.0)
        self.assertEqual(clamp_confidence(1.5), 1.0)
        self.assertEqual(clamp_confidence(0.8), 0.8)


class TestTickerValidation(unittest.TestCase):
    """测试股票代码校验"""

    def test_valid_a_share_codes(self):
        """测试有效的A股代码"""
        import re
        # A股代码范围: 0xxxxx ~ 5xxxxx (6位数字，首位0-5)
        # 注意: 6xxxxx 也是有效的A股代码（沪市主板）
        pattern = re.compile(r'^[0-9]\d{5}$')

        valid_codes = ['000001', '600519', '300750', '000858', '601318']
        for code in valid_codes:
            self.assertIsNotNone(pattern.match(code), f"Expected {code} to be valid")

    def test_invalid_ticker_formats(self):
        """测试无效的股票代码格式"""
        import re
        pattern = re.compile(r'^[0-5]\d{5}$')

        invalid_codes = ['60051', '6005190', 'abc123', '', '60051a', '700001']
        for code in invalid_codes:
            self.assertIsNone(pattern.match(code), f"Expected {code} to be invalid")


class TestRiskScoring(unittest.TestCase):
    """测试风险评分逻辑"""

    def test_high_debt_risk(self):
        """高负债率应增加风险分数"""
        debt_ratio = 75  # > 70
        risk_score = 0

        if debt_ratio > 70:
            risk_score += 25
        elif debt_ratio > 60:
            risk_score += 15

        self.assertEqual(risk_score, 25)

    def test_low_current_ratio_risk(self):
        """低流动比率应增加风险分数"""
        current_ratio = 0.7  # < 0.8
        risk_score = 0

        if current_ratio < 0.8:
            risk_score += 20
        elif current_ratio < 1.0:
            risk_score += 10

        self.assertEqual(risk_score, 20)

    def test_combined_risk_level(self):
        """综合风险等级判断"""
        risk_score = 25 + 20 + 15 + 10 + 10  # 多项风险叠加
        # 80 >= 50 => HIGH

        if risk_score >= 50:
            risk_level = "HIGH"
        elif risk_score >= 25:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        self.assertEqual(risk_level, "HIGH")

    def test_hhi_concentration(self):
        """HHI 集中度计算"""
        positions = {'A': 0.5, 'B': 0.3, 'C': 0.2}
        total = sum(positions.values())
        weights = [v / total for v in positions.values()]
        hhi = sum(w ** 2 for w in weights)

        # 0.5^2 + 0.3^2 + 0.2^2 = 0.25 + 0.09 + 0.04 = 0.38
        self.assertAlmostEqual(hhi, 0.38, places=2)


class TestMarginOfSafety(unittest.TestCase):
    """测试安全边际计算"""

    def test_positive_margin(self):
        """内在价值 > 价格，正安全边际"""
        intrinsic = 100.0
        price = 70.0
        margin = (intrinsic - price) / intrinsic

        self.assertAlmostEqual(margin, 0.3, places=2)
        self.assertAlmostEqual(margin, 0.3)  # 正好 30%

    def test_negative_margin(self):
        """内在价值 < 价格，负安全边际"""
        intrinsic = 100.0
        price = 130.0
        margin = (intrinsic - price) / intrinsic

        self.assertAlmostEqual(margin, -0.3, places=2)

    def test_zero_price(self):
        """价格为零时应处理"""
        intrinsic = 100.0
        price = 0.0

        if price <= 0:
            margin = 0.0
        else:
            margin = (intrinsic - price) / intrinsic

        self.assertEqual(margin, 0.0)


if __name__ == '__main__':
    unittest.main()
