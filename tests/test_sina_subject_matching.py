# -*- coding: utf-8 -*-
"""新浪财务科目确定性匹配测试。"""

import os
import sys
import unittest
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.crawler.subject_matching import SinaSubjectMatcher, normalize_subject_name
from backend.persistence.financial_models import ReportType


@dataclass
class FakeSubject:
    id: int
    code: str
    name: str
    report_type: ReportType
    sina_name: str | None = None


@dataclass
class FakeAlias:
    subject: FakeSubject
    report_type: ReportType
    source_name: str
    normalized_name: str = ""
    context_name: str = ""
    source: str = "sina"
    is_active: bool = True


class TestSinaSubjectMatcher(unittest.TestCase):
    def setUp(self):
        self.standard = FakeSubject(1, "STD001", "标准科目", ReportType.BS)
        self.sina = FakeSubject(2, "STD002", "会计准则名称", ReportType.BS, "新浪主名称")
        self.alias_target = FakeSubject(3, "STD003", "第三科目", ReportType.BS)
        self.interest_income = FakeSubject(4, "ISI002", "利息收入", ReportType.IS)
        self.finance_interest = FakeSubject(5, "ISF006", "财务费用利息收入", ReportType.IS)

        self.matcher = SinaSubjectMatcher(
            [
                self.standard,
                self.sina,
                self.alias_target,
                self.interest_income,
                self.finance_interest,
            ],
            [
                FakeAlias(self.alias_target, ReportType.BS, "历史来源名称"),
                FakeAlias(
                    self.finance_interest,
                    ReportType.IS,
                    "利息收入",
                    context_name="财务费用",
                ),
            ],
        )

    def test_name_exact_precedes_sina_name_exact(self):
        shadow = FakeSubject(6, "STD006", "其他科目", ReportType.BS, "标准科目")
        matcher = SinaSubjectMatcher([self.standard, shadow])

        result = matcher.match("标准科目", "BS")

        self.assertTrue(result.matched)
        self.assertEqual("STD001", result.subject.code)
        self.assertEqual("name_exact", result.method)

    def test_sina_name_exact_precedes_source_alias(self):
        alias_shadow = FakeSubject(7, "STD007", "别名目标", ReportType.BS)
        matcher = SinaSubjectMatcher(
            [self.sina, alias_shadow],
            [FakeAlias(alias_shadow, ReportType.BS, "新浪主名称")],
        )

        result = matcher.match("新浪主名称", "BS")

        self.assertTrue(result.matched)
        self.assertEqual("STD002", result.subject.code)
        self.assertEqual("sina_name_exact", result.method)

    def test_source_alias_precedes_normalized_exact(self):
        result = self.matcher.match("历史来源名称", "BS")

        self.assertTrue(result.matched)
        self.assertEqual("STD003", result.subject.code)
        self.assertEqual("source_alias_exact", result.method)

    def test_normalization_is_deterministic_and_last(self):
        result = self.matcher.match("（一）会计准则名称（损失以-号填列）", "BS")

        self.assertTrue(result.matched)
        self.assertEqual("STD002", result.subject.code)
        self.assertEqual("normalized_exact", result.method)
        self.assertEqual("会计准则名称", normalize_subject_name("（一）会计准则名称（损失以-号填列）"))

    def test_context_alias_resolves_same_name_before_global_name(self):
        result = self.matcher.match("利息收入", "IS", "财务费用")

        self.assertTrue(result.matched)
        self.assertEqual("ISF006", result.subject.code)
        self.assertEqual("context_alias_exact", result.method)

    def test_global_name_applies_without_context(self):
        result = self.matcher.match("利息收入", "IS")

        self.assertTrue(result.matched)
        self.assertEqual("ISI002", result.subject.code)
        self.assertEqual("name_exact", result.method)

    def test_duplicate_exact_candidates_are_ambiguous(self):
        duplicate = FakeSubject(8, "STD008", "标准科目", ReportType.BS)
        matcher = SinaSubjectMatcher([self.standard, duplicate])

        result = matcher.match("标准科目", "BS")

        self.assertFalse(result.matched)
        self.assertEqual("ambiguous", result.issue_type)
        self.assertEqual(("STD001", "STD008"), result.candidate_subject_codes)

    def test_merged_subject_is_rejected(self):
        result = self.matcher.match("应收票据及应收账款", "BS")

        self.assertFalse(result.matched)
        self.assertEqual("rejected", result.issue_type)

    def test_unknown_subject_is_not_fuzzy_matched(self):
        result = self.matcher.match("标准科目明细", "BS")

        self.assertFalse(result.matched)
        self.assertEqual("unmatched", result.issue_type)


if __name__ == "__main__":
    unittest.main()
