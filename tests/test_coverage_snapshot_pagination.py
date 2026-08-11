# -*- coding: utf-8 -*-
"""财务覆盖率快照分页测试。"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.analysis.coverage_service import (
    backfill_snapshot_company_details,
    get_or_create_full_scope_snapshot,
    get_snapshot_gap_items,
    paginate_snapshot_companies,
    save_coverage_snapshot,
    snapshot_has_company_details,
    snapshot_to_dict,
)
from backend.persistence.db import Base
from backend.persistence.financial_models import (
    FinancialCoverageSnapshot,
    FinancialCoverageSnapshotCompany,
)


class TestCoverageSnapshotPagination(unittest.TestCase):
    def test_missing_full_scope_creates_and_reuses_snapshot(self):
        asyncio.run(self._test_missing_full_scope_creates_and_reuses_snapshot())

    async def _test_missing_full_scope_creates_and_reuses_snapshot(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        scan_result = {
            "scope_key": "2024|BS|active",
            "years": [2024],
            "report_types": ["BS"],
            "status_filter": "active",
            "summary": {
                "company_count": 1,
                "matrix_total": 1,
                "complete_cells": 0,
                "partial_cells": 1,
                "missing_cells": 0,
                "gap_company_count": 1,
                "coverage_rate": 0,
            },
            "gap_companies": ["000002"],
            "core_subjects": {},
            "scan_duration_ms": 1,
            "companies": [
                self._company_detail(0, "000002", "部分公司", "partial").company_payload
            ],
        }
        try:
            async with engine.begin() as connection:
                await connection.run_sync(
                    Base.metadata.create_all,
                    tables=[
                        FinancialCoverageSnapshot.__table__,
                        FinancialCoverageSnapshotCompany.__table__,
                    ],
                )

            async with session_factory() as session:
                with patch(
                    "backend.analysis.coverage_service.scan_coverage",
                    new=AsyncMock(return_value=scan_result),
                ) as scan_coverage:
                    first = await get_or_create_full_scope_snapshot(
                        session,
                        years=[2024],
                        report_types=["BS"],
                        status_filter="active",
                    )
                    second = await get_or_create_full_scope_snapshot(
                        session,
                        years=[2024],
                        report_types=["BS"],
                        status_filter="active",
                    )

                self.assertEqual(first.id, second.id)
                self.assertEqual(1, scan_coverage.await_count)
                self.assertTrue(await snapshot_has_company_details(session, first))
        finally:
            await engine.dispose()

    def test_legacy_snapshot_backfills_company_details(self):
        asyncio.run(self._test_legacy_snapshot_backfills_company_details())

    async def _test_legacy_snapshot_backfills_company_details(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(
                    Base.metadata.create_all,
                    tables=[
                        FinancialCoverageSnapshot.__table__,
                        FinancialCoverageSnapshotCompany.__table__,
                    ],
                )

            async with session_factory() as session:
                snapshot = FinancialCoverageSnapshot(
                    scope_key="2024|BS|active",
                    years=[2024],
                    report_types=["BS"],
                    status_filter="active",
                    source="legacy",
                    company_count=1,
                    matrix_total=1,
                    complete_cells=0,
                    partial_cells=1,
                    missing_cells=0,
                    gap_company_count=1,
                    coverage_rate=0,
                    summary={"company_count": 1},
                    gap_companies=["000002"],
                    companies_payload=(
                        '[{"stock_code":"000002","stock_name":"部分公司",'
                        '"overall_status":"partial","coverage_rate":0,'
                        '"complete_cells":0,"partial_cells":1,"missing_cells":0,'
                        '"expected_cells":1,"cells":[]}]'
                    ),
                    core_subjects={},
                )
                session.add(snapshot)
                await session.commit()

                self.assertFalse(await snapshot_has_company_details(session, snapshot))
                self.assertTrue(await backfill_snapshot_company_details(session, snapshot))
                self.assertTrue(await snapshot_has_company_details(session, snapshot))
        finally:
            await engine.dispose()

    def test_save_snapshot_writes_company_details(self):
        asyncio.run(self._test_save_snapshot_writes_company_details())

    async def _test_save_snapshot_writes_company_details(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(
                    Base.metadata.create_all,
                    tables=[
                        FinancialCoverageSnapshot.__table__,
                        FinancialCoverageSnapshotCompany.__table__,
                    ],
                )

            async with session_factory() as session:
                snapshot = await save_coverage_snapshot(
                    session,
                    {
                        "scope_key": "2024|BS|active",
                        "years": [2024],
                        "report_types": ["BS"],
                        "status_filter": "active",
                        "summary": {
                            "company_count": 1,
                            "matrix_total": 1,
                            "complete_cells": 0,
                            "partial_cells": 1,
                            "missing_cells": 0,
                            "gap_company_count": 1,
                            "coverage_rate": 0,
                        },
                        "gap_companies": ["000002"],
                        "core_subjects": {},
                        "scan_duration_ms": 1,
                        "companies": [
                            self._company_detail(
                                0,
                                "000002",
                                "部分公司",
                                "partial",
                            ).company_payload
                        ],
                    },
                    source="test",
                )
                row_count = await session.scalar(
                    select(func.count())
                    .select_from(FinancialCoverageSnapshotCompany)
                    .where(FinancialCoverageSnapshotCompany.snapshot_id == snapshot.id)
                )

                self.assertIsNone(snapshot.companies_payload)
                self.assertEqual(1, row_count)
                self.assertTrue(await snapshot_has_company_details(session, snapshot))
        finally:
            await engine.dispose()

    def test_snapshot_company_details_support_sql_pagination(self):
        asyncio.run(self._test_snapshot_company_details_support_sql_pagination())

    async def _test_snapshot_company_details_support_sql_pagination(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(
                    Base.metadata.create_all,
                    tables=[
                        FinancialCoverageSnapshot.__table__,
                        FinancialCoverageSnapshotCompany.__table__,
                    ],
                )

            async with session_factory() as session:
                snapshot = FinancialCoverageSnapshot(
                    scope_key="2024|BS|active",
                    years=[2024],
                    report_types=["BS"],
                    status_filter="active",
                    source="test",
                    company_count=3,
                    matrix_total=3,
                    complete_cells=1,
                    partial_cells=1,
                    missing_cells=1,
                    gap_company_count=2,
                    coverage_rate=0.333333,
                    summary={"company_count": 3},
                    gap_companies=["000002", "000003"],
                    companies_payload="[]",
                    core_subjects={},
                )
                session.add(snapshot)
                await session.flush()
                session.add_all(
                    [
                        self._company_detail(snapshot.id, "000001", "完整公司", "complete"),
                        self._company_detail(snapshot.id, "000002", "部分公司", "partial"),
                        self._company_detail(snapshot.id, "000003", "缺失公司", "missing"),
                    ]
                )
                await session.commit()

                self.assertTrue(await snapshot_has_company_details(session, snapshot))

                second_page = await paginate_snapshot_companies(
                    session,
                    snapshot,
                    page=2,
                    page_size=1,
                    include_cells=False,
                )
                self.assertEqual(3, second_page["total"])
                self.assertEqual(["000002"], [item["stock_code"] for item in second_page["companies"]])
                self.assertNotIn("cells", second_page["companies"][0])

                gap_page = await paginate_snapshot_companies(
                    session,
                    snapshot,
                    only_gaps=True,
                    page=1,
                    page_size=10,
                    search="部分",
                )
                self.assertEqual(1, gap_page["total"])
                self.assertEqual("000002", gap_page["companies"][0]["stock_code"])

                gaps = await get_snapshot_gap_items(session, snapshot, limit=1)
                self.assertEqual(1, len(gaps))
                self.assertEqual("000002", gaps[0]["stock_code"])
                self.assertEqual("BS", gaps[0]["report_type"])
        finally:
            await engine.dispose()

    def test_legacy_snapshot_payload_remains_readable(self):
        snapshot = FinancialCoverageSnapshot(
            id=1,
            scope_key="2024|BS|active",
            years=[2024],
            report_types=["BS"],
            status_filter="active",
            source="legacy",
            company_count=1,
            matrix_total=1,
            complete_cells=1,
            partial_cells=0,
            missing_cells=0,
            gap_company_count=0,
            coverage_rate=1,
            summary={"company_count": 1},
            gap_companies=[],
            companies_payload=(
                '[{"stock_code":"000001","stock_name":"平安银行",'
                '"overall_status":"complete","cells":[]}]'
            ),
            core_subjects={},
        )

        result = snapshot_to_dict(snapshot)

        self.assertEqual("000001", result["companies"][0]["stock_code"])
        self.assertTrue(result["from_snapshot"])

    @staticmethod
    def _company_detail(
        snapshot_id: int,
        stock_code: str,
        stock_name: str,
        overall_status: str,
    ) -> FinancialCoverageSnapshotCompany:
        cell_status = "complete" if overall_status == "complete" else overall_status
        return FinancialCoverageSnapshotCompany(
            snapshot_id=snapshot_id,
            stock_code=stock_code,
            stock_name=stock_name,
            overall_status=overall_status,
            coverage_rate=1 if overall_status == "complete" else 0,
            complete_cells=1 if overall_status == "complete" else 0,
            partial_cells=1 if overall_status == "partial" else 0,
            missing_cells=1 if overall_status == "missing" else 0,
            expected_cells=1,
            company_payload={
                "stock_code": stock_code,
                "stock_name": stock_name,
                "overall_status": overall_status,
                "cells": [
                    {
                        "year": 2024,
                        "report_type": "BS",
                        "status": cell_status,
                        "core_hit_rate": 1 if cell_status == "complete" else 0,
                        "missing_required": [],
                        "missing_optional": [],
                    }
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()
