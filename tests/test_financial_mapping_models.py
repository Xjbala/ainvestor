# -*- coding: utf-8 -*-
"""财务采集映射数据模型与审核目录契约测试。"""

import os
import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.persistence.db import Base

from backend.persistence.financial_models import (
    AccountCategory,
    AccountSubject,
    AccountSubjectSourceAlias,
    Company,
    Exchange,
    FinancialData,
    FinancialMatchIssue,
    Industry,
    ValuationForecast,
)
from backend.scripts.sina_mapping_catalog import load_sina_subject_mapping_catalog
from backend.scripts.bank_subject_catalog import load_bank_subject_catalog


class TestFinancialMappingModels(unittest.TestCase):
    def test_new_data_models_are_traceable(self):
        alias_columns = set(AccountSubjectSourceAlias.__table__.c.keys())
        issue_columns = set(FinancialMatchIssue.__table__.c.keys())
        financial_data_columns = set(FinancialData.__table__.c.keys())

        self.assertTrue({
            "subject_id", "source", "report_type", "source_name",
            "normalized_name", "context_name", "note", "is_active",
        }.issubset(alias_columns))
        self.assertTrue({
            "raw_subject_name", "context_name", "raw_value", "issue_type",
            "candidate_subject_codes", "crawl_task_id", "occurrence_count",
        }.issubset(issue_columns))
        self.assertTrue({
            "source_subject_name", "source_context_name", "subject_match_method",
        }.issubset(financial_data_columns))

    def test_financial_special_case_schema_is_not_used(self):
        self.assertIn("legacy_is_financial", AccountSubject.__mapper__.attrs.keys())
        self.assertEqual(
            "is_financial", AccountSubject.__mapper__.attrs.legacy_is_financial.columns[0].name
        )
        self.assertNotIn("financial_subject_mappings", AccountSubject.metadata.tables)

    def test_new_data_models_create_in_sqlite(self):
        engine = create_engine("sqlite:///:memory:")
        tables = [
            Exchange.__table__,
            Industry.__table__,
            Company.__table__,
            AccountCategory.__table__,
            AccountSubject.__table__,
            FinancialData.__table__,
            AccountSubjectSourceAlias.__table__,
            FinancialMatchIssue.__table__,
        ]
        try:
            Base.metadata.create_all(engine, tables=tables)
            inspector = inspect(engine)
            self.assertTrue(inspector.has_table("account_subject_source_aliases"))
            self.assertTrue(inspector.has_table("financial_match_issues"))
            columns = {
                column["name"]
                for column in inspector.get_columns("financial_data")
            }
            self.assertTrue({
                "source_subject_name", "source_context_name", "subject_match_method",
            }.issubset(columns))
        finally:
            engine.dispose()

    def test_catalog_has_unique_alias_keys_and_no_rejected_aliases(self):
        catalog = load_sina_subject_mapping_catalog()
        alias_keys = {
            (
                item["report_type"],
                item["source_name"],
                item.get("context_name", ""),
            )
            for item in catalog["aliases"]
        }
        rejected_keys = {
            (item["report_type"], item["source_name"])
            for item in catalog["rejected"]
        }

        self.assertEqual(len(alias_keys), len(catalog["aliases"]))
        for alias in catalog["aliases"]:
            self.assertNotIn(
                (alias["report_type"], alias["source_name"]),
                rejected_keys,
            )

    def test_valuation_forecast_unique_key_excludes_json_parameters(self):
        unique_constraints = {
            constraint.name: tuple(column.name for column in constraint.columns)
            for constraint in ValuationForecast.__table__.constraints
            if constraint.name
        }

        self.assertEqual(
            ("company_code", "valuation_method", "base_year", "forecast_year"),
            unique_constraints["uq_valuation_forecast"],
        )
        self.assertNotIn("parameters", unique_constraints["uq_valuation_forecast"])

    def test_catalog_targets_are_present_in_subject_initializer(self):
        initializer = Path(__file__).parents[1] / "backend/scripts/init_subjects.py"
        initializer_text = initializer.read_text(encoding="utf-8")
        catalog = load_sina_subject_mapping_catalog()
        catalog_codes = {
            item["subject_code"]
            for item in [*catalog["primary_sina_names"], *catalog["aliases"]]
        }

        missing_codes = sorted(
            code
            for code in catalog_codes
            if f"'code': '{code}'" not in initializer_text
        )
        self.assertEqual([], missing_codes)

    def test_bank_catalog_standard_targets_are_present_in_subject_initializer(self):
        """银行目录中引用标准科目（非银行专属）的别名目标必须在 init_subjects 中有定义。"""
        initializer = Path(__file__).parents[1] / "backend/scripts/init_subjects.py"
        initializer_text = initializer.read_text(encoding="utf-8")
        catalog = load_bank_subject_catalog()

        bank_subject_codes = {entry["code"] for entry in catalog["subjects"]}
        alias_target_codes = {entry["subject_code"] for entry in catalog["aliases"]}
        standard_targets = alias_target_codes - bank_subject_codes

        missing_codes = sorted(
            code
            for code in standard_targets
            if f"'code': '{code}'" not in initializer_text
        )
        self.assertEqual([], missing_codes,
            f"银行别名引用的标准科目在 init_subjects.py 中缺失: {missing_codes}")

    def test_wacc_interest_codes_exclude_fair_value_and_credit_impairment(self):
        """WACC 利息费用科目不得使用公允价值变动收益(ISF013)或信用减值损失(ISF014)。"""
        from backend.valuation.wacc import WACCService

        self.assertNotIn("ISF013", WACCService.INTEREST_CODES)
        self.assertNotIn("ISF014", WACCService.INTEREST_CODES)
        self.assertIn("ISF005", WACCService.INTEREST_CODES)

    def test_wacc_ebt_codes_exclude_non_operating_expense(self):
        """WACC 税前利润科目只应为 ISF019（利润总额），不含营业外支出 ISF018。"""
        from backend.valuation.wacc import WACCService

        self.assertEqual(["ISF019"], WACCService.EBT_CODES)
        self.assertNotIn("ISF018", WACCService.EBT_CODES)


if __name__ == "__main__":
    unittest.main()
