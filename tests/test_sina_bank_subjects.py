# -*- coding: utf-8 -*-
"""000001 银行报表科目目录、层级匹配和验证 profile 测试。"""

import json
import os
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.analysis.financial_validation import (
    ValidationStatus,
    evaluate_cell_completeness,
    validate_period,
)
from backend.crawler.subject_matching import SinaSubjectMatcher
from backend.persistence.financial_models import ReportType
from backend.scripts.bank_subject_catalog import load_bank_subject_catalog


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
    normalized_name: str
    context_name: str = ""
    source: str = "sina"
    is_active: bool = True


class TestSinaBankSubjects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = load_bank_subject_catalog()
        cls.subjects = []
        cls.subjects_by_code = {}
        report_types = {"BS": ReportType.BS, "IS": ReportType.IS, "CF": ReportType.CF}
        for index, entry in enumerate(catalog["subjects"], start=1):
            subject = FakeSubject(
                index,
                entry["code"],
                entry["name"],
                report_types[entry["report_type"]],
                entry.get("sina_name"),
            )
            cls.subjects.append(subject)
            cls.subjects_by_code[subject.code] = subject

        # 已有目录中被银行新浪字段复用的标准科目。
        existing = [
            FakeSubject(100, "BSA005", "衍生金融资产", ReportType.BS),
            FakeSubject(101, "BSA101", "发放贷款和垫款", ReportType.BS, "发放贷款及垫款"),
            FakeSubject(102, "BSA118", "递延所得税资产", ReportType.BS),
            FakeSubject(103, "BSL003", "拆入资金", ReportType.BS),
            FakeSubject(104, "BSL005", "衍生金融负债", ReportType.BS),
            FakeSubject(105, "ISI002", "利息收入", ReportType.IS),
            FakeSubject(106, "ISI004", "手续费及佣金收入", ReportType.IS),
            FakeSubject(107, "ISC002", "利息支出", ReportType.IS),
            FakeSubject(108, "ISC003", "手续费及佣金支出", ReportType.IS),
            FakeSubject(109, "ISF013", "公允价值变动收益", ReportType.IS),
            FakeSubject(110, "ISF020", "所得税费用", ReportType.IS),
            FakeSubject(111, "ISF026", "归属于母公司所有者的净利润", ReportType.IS),
            FakeSubject(112, "CFIV003", "处置固定资产收回的现金", ReportType.CF),
            FakeSubject(113, "CFFN001", "吸收投资收到的现金", ReportType.CF),
            FakeSubject(114, "CFFN006", "偿还债务支付的现金", ReportType.CF),
            FakeSubject(115, "BSE010", "归属于母公司所有者权益合计", ReportType.BS),
            FakeSubject(116, "BSA001", "货币资金", ReportType.BS),
            FakeSubject(117, "BSE001", "实收资本（或股本）", ReportType.BS),
            FakeSubject(118, "BSE012", "所有者权益（或股东权益）合计", ReportType.BS),
        ]
        cls.subjects.extend(existing)
        cls.subjects_by_code.update({subject.code: subject for subject in existing})
        aliases = [
            FakeAlias(
                cls.subjects_by_code[entry["subject_code"]],
                report_types[entry["report_type"]],
                entry["source_name"],
                entry["source_name"],
                entry.get("context_name", ""),
            )
            for entry in catalog["aliases"]
        ]
        cls.matcher = SinaSubjectMatcher(cls.subjects, aliases)
        fixture_path = Path(__file__).parent / "fixtures" / "sina_000001_bank_20260331.json"
        cls.fixture_rows = json.loads(fixture_path.read_text(encoding="utf-8"))["rows"]

    def _match(self, raw_name, report_type, context_name=""):
        return self.matcher.match(raw_name, report_type, context_name)

    def test_bank_fixture_new_main_subjects_match(self):
        expected = {
            "现金及存放中央银行款项": "BSA023",
            "存放同业款项": "BSA025",
            "发放贷款及垫款净额": "BSA026",
            "减:贷款损失准备": "BSA030",
            "同业存入及拆入": "BSL025",
            "客户存款(吸收存款)": "BSL026",
            "净利息收入": "ISI006",
            "手续费及佣金净收入": "ISI007",
            "营业支出": "ISC011",
            "拆入资金现金流入": "CFO021",
            "吸收的卖出回购项净额": "CFO022",
            "为交易目的而持有的金融资产净增加额": "CFO026",
            "发行债券收到的现金": "CFFN012",
            "偿付利息所支付的现金": "CFFN014",
        }
        for row in self.fixture_rows:
            expected_code = expected.get(row["raw_subject_name"])
            if not expected_code:
                continue
            result = self._match(
                row["raw_subject_name"], row["report_type"], row["source_context_name"]
            )
            self.assertTrue(result.matched, row)
            self.assertEqual(expected_code, result.subject.code, row)

    def test_bank_context_details_do_not_map_to_cash(self):
        cash_detail = self._match("其中:现金", "BS", "现金及存放中央银行款项")
        central_bank = self._match("存放中央银行款", "BS", "现金及存放中央银行款项")

        self.assertEqual("BSA027", cash_detail.subject.code)
        self.assertEqual("BSA028", central_bank.subject.code)
        self.assertNotEqual("BSA001", cash_detail.subject.code)
        self.assertNotEqual("BSA001", central_bank.subject.code)

    def test_bank_income_context_disambiguates_interest_income(self):
        bank_income = self._match("利息收入", "IS", "净利息收入")

        self.assertTrue(bank_income.matched)
        self.assertEqual("ISI002", bank_income.subject.code)
        self.assertEqual("context_alias_exact", bank_income.method)

    def test_existing_subjects_are_reused_for_equivalent_bank_fields(self):
        debt_repayment = self._match("偿还债务所支付的现金", "CF")
        derivatives = self._match("衍生金融工具资产", "BS")
        share_capital = self._match("股本", "BS")
        shareholders_equity = self._match("股东权益", "BS")

        self.assertEqual("CFFN006", debt_repayment.subject.code)
        self.assertEqual("BSA005", derivatives.subject.code)
        self.assertEqual("BSE001", share_capital.subject.code)
        self.assertEqual("BSE012", shareholders_equity.subject.code)

    def test_bank_hierarchy_and_measurement_details_are_rejected(self):
        result = self._match("固定资产净额", "BS")
        perpetual_bond = self._match("其中：永续债", "BS", "其他权益工具")
        other_comprehensive_income = self._match(
            "其他债权投资公允价值变动",
            "IS",
            "归属于母公司所有者的其他综合收益",
        )

        self.assertFalse(result.matched)
        self.assertEqual("rejected", result.issue_type)
        self.assertEqual("rejected", perpetual_bond.issue_type)
        self.assertEqual("rejected", other_comprehensive_income.issue_type)

    def test_bank_profile_uses_bank_core_subjects(self):
        bank_bs_codes = {"BSA023", "BSA026", "BSA121", "BSL026", "BSL112", "BSE010"}
        bank_result = evaluate_cell_completeness("BS", bank_bs_codes, profile="bank")
        default_result = evaluate_cell_completeness("BS", bank_bs_codes, profile="default")

        self.assertEqual("complete", bank_result["status"])
        self.assertEqual("partial", default_result["status"])

    def test_bank_period_validation_accepts_bank_core_set(self):
        items = [
            {"subject_code": "ISI006", "value": 100.0},
            {"subject_code": "ISF016", "value": 80.0},
            {"subject_code": "ISF019", "value": 80.0},
            {"subject_code": "ISF020", "value": 10.0},
            {"subject_code": "ISF021", "value": 70.0},
        ]
        validation = validate_period("IS", "2026-03-31", items, profile="bank")

        self.assertNotEqual(ValidationStatus.FAIL, validation.status)
        self.assertEqual(5, validation.core_required_present)


if __name__ == "__main__":
    unittest.main()
