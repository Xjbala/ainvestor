# -*- coding: utf-8 -*-
"""
估值融合 V2 单元测试：行业画像、敏感性、权重、SOTP、三角加权。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.valuation.industry_profiles import (
    get_industry_profile,
    method_weight,
    resolve_profile_key,
)
from backend.valuation.scenarios import (
    build_bull_base_bear_prices,
    build_sensitivity_grid,
    rating_from_upside,
)
from backend.valuation.sotp import SOTPValuationService
from backend.valuation.triangulate import TriangulationService


class TestIndustryProfiles(unittest.TestCase):
    def test_bank_profile(self):
        p = get_industry_profile("商业银行")
        self.assertEqual(p["profile_key"], "bank")
        self.assertEqual(p["relative_primary"], "pb")
        self.assertEqual(p["methods"]["DCF"], "skip")

    def test_consumer_profile(self):
        self.assertEqual(resolve_profile_key("白酒制造"), "consumer_staples")

    def test_default_profile(self):
        p = get_industry_profile(None)
        self.assertEqual(p["profile_key"], "default")

    def test_method_weight_bank_suppresses_dcf(self):
        w = method_weight(
            "银行",
            has_dcf=True,
            has_ri=True,
            has_relative=True,
        )
        self.assertEqual(w["DCF"], 0.0)
        self.assertGreater(w["RELATIVE"], 0.0)
        self.assertAlmostEqual(sum(w.values()), 1.0, places=3)

    def test_method_weight_normal_company(self):
        w = method_weight(
            "白酒",
            has_dcf=True,
            has_ri=True,
            has_relative=True,
        )
        self.assertGreater(w["DCF"], 0.0)
        self.assertAlmostEqual(sum(w.values()), 1.0, places=3)

    def test_method_weight_only_relative(self):
        w = method_weight(
            None,
            has_dcf=False,
            has_ri=False,
            has_relative=True,
        )
        self.assertEqual(w["RELATIVE"], 1.0)


class TestScenarios(unittest.TestCase):
    def test_sensitivity_grid_shape(self):
        grid = build_sensitivity_grid(
            base_wacc=0.10,
            base_g=0.025,
            last_fcf=1e8,
            pv_projected_fcf=3e8,
            net_debt=0,
            shares=1e8,
        )
        self.assertEqual(len(grid["wacc_axis"]), 5)
        self.assertEqual(len(grid["g_axis"]), 5)
        self.assertEqual(len(grid["grid"]), 5)
        self.assertEqual(len(grid["grid"][0]), 5)
        # base-ish cell should be positive
        self.assertIsNotNone(grid["grid"][2][2])
        self.assertGreater(grid["grid"][2][2], 0)

    def test_sensitivity_invalid_wacc_leq_g(self):
        grid = build_sensitivity_grid(
            base_wacc=0.02,
            base_g=0.03,
            last_fcf=1e8,
            pv_projected_fcf=1e8,
            net_debt=0,
            shares=1e8,
            wacc_deltas=(0.0,),
            g_values=(0.03,),
        )
        self.assertIsNone(grid["grid"][0][0])

    def test_bull_base_bear(self):
        s = build_bull_base_bear_prices(100.0)
        self.assertGreater(s["bull"]["price"], s["base"]["price"])
        self.assertLess(s["bear"]["price"], s["base"]["price"])

    def test_rating_from_upside(self):
        self.assertEqual(rating_from_upside(35), "STRONG_BUY")
        self.assertEqual(rating_from_upside(20), "BUY")
        self.assertEqual(rating_from_upside(0), "HOLD")
        self.assertEqual(rating_from_upside(-20), "REDUCE")
        self.assertEqual(rating_from_upside(-40), "SELL")
        self.assertEqual(rating_from_upside(None), "HOLD")


class TestTriangulateBlend(unittest.TestCase):
    def test_blend_equal(self):
        svc = TriangulationService(session=None)  # type: ignore
        methods = [
            {"method": "DCF", "applicable": True, "implied_price": 100.0},
            {"method": "RI", "applicable": True, "implied_price": 120.0},
            {"method": "RELATIVE", "applicable": True, "implied_price": 80.0},
        ]
        weights = {"DCF": 0.4, "RI": 0.2, "RELATIVE": 0.4, "SOTP": 0.0}
        blended, used = svc._blend(methods, weights)
        expected = 100 * 0.4 + 120 * 0.2 + 80 * 0.4
        self.assertAlmostEqual(blended, expected, places=4)
        self.assertAlmostEqual(sum(used.values()), 1.0, places=3)

    def test_blend_skips_inapplicable(self):
        svc = TriangulationService(session=None)  # type: ignore
        methods = [
            {"method": "DCF", "applicable": False, "implied_price": None},
            {"method": "RI", "applicable": True, "implied_price": 50.0},
            {"method": "RELATIVE", "applicable": True, "implied_price": 100.0},
        ]
        weights = {"DCF": 0.5, "RI": 0.25, "RELATIVE": 0.25, "SOTP": 0.0}
        blended, used = svc._blend(methods, weights)
        self.assertEqual(used.get("DCF", 0), 0.0)
        self.assertAlmostEqual(blended, (50 * 0.25 + 100 * 0.25) / 0.5, places=4)

    def test_headline_contains_price(self):
        svc = TriangulationService(session=None)  # type: ignore
        h = svc._headline(
            {"stock_name": "测试", "stock_code": "000001"},
            10.5,
            10.0,
            5.0,
            [{"method": "DCF", "applicable": True, "implied_price": 11.0}],
            "medium",
        )
        self.assertIn("10.50", h)
        self.assertIn("测试", h)


class TestSOTP(unittest.TestCase):
    def test_sotp_from_segments(self):
        segments = [
            {"name": "Cloud", "ebitda": 100, "revenue": 400, "multiple": 20, "multiple_type": "ev_ebitda"},
            {"name": "Hardware", "ebitda": 50, "revenue": 300, "multiple": 8, "multiple_type": "ev_ebitda"},
        ]
        result = SOTPValuationService.valuate_from_segments(
            segments,
            net_debt=200,
            cash=50,
            shares=100,
            current_price=20.0,
            corporate_cost=100,
        )
        self.assertTrue(result["applicable"])
        # EV = 100*20 + 50*8 = 2000+400=2400; -corp 100 -net_debt 200 +cash 50 = 2150; /100 = 21.5
        self.assertAlmostEqual(result["valuation"]["intrinsic_value_per_share"], 21.5, places=2)
        self.assertIn("discount_pct", result)

    def test_sotp_empty_segments(self):
        result = SOTPValuationService.valuate_from_segments([], shares=100)
        self.assertFalse(result["applicable"])
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
