# -*- coding: utf-8 -*-
"""分部抽取器单元测试（纯规则，无 LLM）。"""

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.crawler.qualitative.segment_extractor import SegmentExtractor
from backend.valuation.sotp import SOTPValuationService


SAMPLE_MD = """
# 第四节 经营情况讨论与分析

## 主营业务分析

### 按产品构成列示

| 产品 | 营业收入 | 营业利润 | 同比 |
| --- | --- | --- | --- |
| 云计算 | 120.5 | 30.2 | 15.0% |
| 硬件设备 | 80.3 | 10.1 | -5.0% |
| 软件服务 | 45.0 | 12.0 | 8.0% |
| 合计 | 245.8 | 52.3 | 6.0% |

### 其他
无关内容
"""


class TestSegmentExtractor(unittest.TestCase):
    def setUp(self):
        self.ex = SegmentExtractor()

    def test_extract_product_table(self):
        result = self.ex.extract(
            SAMPLE_MD,
            company_code="000001",
            report_period=date(2024, 12, 31),
            use_llm_fallback=False,
        )
        self.assertGreaterEqual(result["count"], 2)
        names = {s["segment_name"] for s in result["segments"]}
        self.assertIn("云计算", names)
        self.assertNotIn("合计", names)
        # 亿元启发式 → 元
        cloud = next(s for s in result["segments"] if s["segment_name"] == "云计算")
        self.assertIsNotNone(cloud["revenue"])
        self.assertGreater(cloud["revenue"], 1e8)

    def test_sotp_from_extracted(self):
        result = self.ex.extract(SAMPLE_MD, use_llm_fallback=False)
        segs = []
        for s in result["segments"]:
            segs.append({
                "name": s["segment_name"],
                "revenue": s["revenue"] or 0,
                "ebitda": s["operating_income"] or 0,
                "multiple": 12,
                "multiple_type": "ev_ebitda",
            })
        sotp = SOTPValuationService.valuate_from_segments(
            segs,
            net_debt=0,
            cash=0,
            shares=1e9,
            current_price=10.0,
            corporate_cost=0,
        )
        self.assertTrue(sotp["applicable"])
        self.assertGreater(sotp["valuation"]["intrinsic_value_per_share"], 0)

    def test_empty_markdown(self):
        result = self.ex.extract("", use_llm_fallback=False)
        self.assertEqual(result["count"] if "count" in result else len(result["segments"]), 0)


if __name__ == "__main__":
    unittest.main()
