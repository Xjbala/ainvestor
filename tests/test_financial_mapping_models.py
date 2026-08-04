# -*- coding: utf-8 -*-
"""财务采集映射数据模型与审核目录契约测试。"""

import os
import sys
import unittest

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
)
from backend.scripts.sina_mapping_catalog import load_sina_subject_mapping_catalog


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


if __name__ == "__main__":
    unittest.main()
