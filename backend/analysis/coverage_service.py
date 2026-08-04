# -*- coding: utf-8 -*-
"""
财务覆盖率扫描与快照服务

- 在线扫描 公司×报表×年份 核心科目完整度
- 落库快照，供看板快速读取
- 补采任务结束后可自动刷新快照
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..persistence.financial_models import (
    Company,
    CompanyStatus,
    FinancialCoverageSnapshot,
    FinancialData,
    Industry,
    ReportType,
)
from .financial_validation import (
    BANK_CORE_SUBJECTS,
    CORE_SUBJECTS,
    build_coverage_matrix,
    core_subjects_for_profile,
    validation_profile_for_industry,
)

logger = logging.getLogger(__name__)


def default_coverage_years(years: Optional[Sequence[int]] = None) -> List[int]:
    if years:
        cleaned = sorted({int(y) for y in years if 1990 <= int(y) <= 2100})
        if cleaned:
            return cleaned
    end_year = date.today().year - 1
    return list(range(end_year - 4, end_year + 1))


def normalize_report_types(report_types: Optional[Sequence[str]] = None) -> List[str]:
    raw = list(report_types or ["BS", "IS", "CF"])
    rts = [str(rt).strip().upper() for rt in raw if str(rt).strip()]
    rts = [rt for rt in rts if rt in ("BS", "IS", "CF")]
    return rts or ["BS", "IS", "CF"]


def build_scope_key(
    years: Sequence[int],
    report_types: Sequence[str],
    status_filter: str = "active",
) -> str:
    y = ",".join(str(i) for i in sorted(int(x) for x in years))
    r = ",".join(normalize_report_types(report_types))
    s = (status_filter or "active").strip().lower()
    return f"{y}|{r}|{s}"


def core_subjects_payload(report_types: Sequence[str]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """返回默认和银行 profile 的核心科目定义。"""
    profiles = {"default": CORE_SUBJECTS, "bank": BANK_CORE_SUBJECTS}
    return {
        profile: {
            rt: [
                {
                    "code": s["code"],
                    "name": s["name"],
                    "required": bool(s.get("required")),
                }
                for s in definitions.get(rt, [])
            ]
            for rt in report_types
        }
        for profile, definitions in profiles.items()
    }


async def load_present_index(
    session: AsyncSession,
    stock_codes: List[str],
    years: List[int],
    report_types: List[str],
) -> Dict[tuple, set]:
    """加载 (company, report_type, year) -> present core subject codes。"""
    if not stock_codes or not years:
        return {}

    year_min, year_max = min(years), max(years)
    rt_enums: List[ReportType] = []
    core_codes: List[str] = []
    for rt in report_types:
        try:
            rt_enums.append(ReportType(rt.upper()))
        except ValueError:
            continue
        for profile in ("default", "bank"):
            for spec in core_subjects_for_profile(rt.upper(), profile):
                code = spec.get("code")
                if code:
                    core_codes.append(str(code))
    if not rt_enums:
        return {}
    core_codes = sorted(set(core_codes))

    batch_size = 800
    rows = []
    for i in range(0, len(stock_codes), batch_size):
        batch = stock_codes[i: i + batch_size]
        stmt = select(
            FinancialData.company_code,
            FinancialData.report_type,
            FinancialData.report_date,
            FinancialData.subject_code,
        ).where(
            FinancialData.company_code.in_(batch),
            FinancialData.report_type.in_(rt_enums),
            FinancialData.report_date >= date(year_min, 1, 1),
            FinancialData.report_date <= date(year_max, 12, 31),
        )
        if core_codes:
            stmt = stmt.where(FinancialData.subject_code.in_(core_codes))
        rows.extend((await session.execute(stmt)).all())

    annual: Dict[tuple, set] = {}
    any_period: Dict[tuple, set] = {}
    target_years = set(years)

    for company_code, report_type, report_date, subject_code in rows:
        if not company_code or not report_date or not subject_code:
            continue
        y = report_date.year
        if y not in target_years:
            continue
        rt = report_type.value if hasattr(report_type, "value") else str(report_type)
        key = (company_code, rt, y)
        any_period.setdefault(key, set()).add(subject_code)
        if report_date.month == 12:
            annual.setdefault(key, set()).add(subject_code)

    present_index: Dict[tuple, set] = {}
    for key, codes in any_period.items():
        present_index[key] = annual.get(key) or codes
    return present_index


async def scan_coverage(
    session: AsyncSession,
    *,
    years: Optional[Sequence[int]] = None,
    report_types: Optional[Sequence[str]] = None,
    status_filter: str = "active",
    stock_codes: Optional[Sequence[str]] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """执行一次在线覆盖率扫描（不落库）。"""
    from sqlalchemy import or_

    t0 = time.perf_counter()
    year_list = default_coverage_years(years)
    rt_list = normalize_report_types(report_types)

    query = select(
        Company.stock_code,
        Company.stock_name,
        Company.company_name,
        Industry.code,
        Industry.name,
    ).outerjoin(Industry, Company.industry_id == Industry.id)
    if status_filter != "all":
        query = query.where(Company.status == CompanyStatus.ACTIVE)
    if stock_codes:
        codes = [c.strip() for c in stock_codes if str(c).strip()]
        if codes:
            query = query.where(Company.stock_code.in_(codes))
    if search:
        query = query.where(
            or_(
                Company.stock_code.contains(search),
                Company.stock_name.contains(search),
                Company.company_name.contains(search),
            )
        )
    query = query.order_by(Company.stock_code.asc())
    company_rows = (await session.execute(query)).all()
    companies = [
        {
            "stock_code": code,
            "stock_name": stock_name or code,
            "validation_profile": validation_profile_for_industry(
                industry_code, industry_name, stock_name or company_name
            ),
        }
        for code, stock_name, company_name, industry_code, industry_name in company_rows
    ]
    all_codes = [c["stock_code"] for c in companies]
    profile_by_company = {
        company["stock_code"]: company["validation_profile"]
        for company in companies
    }

    present_index = await load_present_index(session, all_codes, year_list, rt_list)
    matrix = build_coverage_matrix(
        companies=companies,
        years=year_list,
        report_types=rt_list,
        present_index=present_index,
        profile_by_company=profile_by_company,
    )
    duration_ms = int((time.perf_counter() - t0) * 1000)

    return {
        "years": matrix["years"],
        "report_types": matrix["report_types"],
        "status_filter": status_filter,
        "summary": matrix["summary"],
        "gap_companies": matrix["gap_companies"],
        "companies": matrix["companies"],
        "core_subjects": core_subjects_payload(rt_list),
        "scan_duration_ms": duration_ms,
        "scope_key": build_scope_key(year_list, rt_list, status_filter),
        "from_snapshot": False,
        "snapshot_id": None,
        "scanned_at": None,
    }


async def save_coverage_snapshot(
    session: AsyncSession,
    scan_result: Dict[str, Any],
    *,
    source: str = "manual_scan",
    trigger_task_id: Optional[str] = None,
    created_by: Optional[str] = None,
) -> FinancialCoverageSnapshot:
    """将扫描结果落库为快照。"""
    summary = scan_result.get("summary") or {}
    years = list(scan_result.get("years") or [])
    report_types = list(scan_result.get("report_types") or [])
    status_filter = scan_result.get("status_filter") or "active"
    scope_key = scan_result.get("scope_key") or build_scope_key(years, report_types, status_filter)

    snap = FinancialCoverageSnapshot(
        scope_key=scope_key,
        years=years,
        report_types=report_types,
        status_filter=status_filter,
        source=source,
        trigger_task_id=trigger_task_id,
        company_count=int(summary.get("company_count") or 0),
        matrix_total=int(summary.get("matrix_total") or 0),
        complete_cells=int(summary.get("complete_cells") or 0),
        partial_cells=int(summary.get("partial_cells") or 0),
        missing_cells=int(summary.get("missing_cells") or 0),
        gap_company_count=int(summary.get("gap_company_count") or 0),
        coverage_rate=Decimal(str(summary.get("coverage_rate") or 0)),
        summary=summary,
        gap_companies=list(scan_result.get("gap_companies") or []),
        companies_payload=json.dumps(scan_result.get("companies") or [], ensure_ascii=False),
        core_subjects=scan_result.get("core_subjects"),
        scan_duration_ms=int(scan_result.get("scan_duration_ms") or 0),
        created_by=created_by,
    )
    session.add(snap)
    await session.commit()
    await session.refresh(snap)
    logger.info(
        "Saved coverage snapshot id=%s scope=%s coverage=%.4f gaps=%s source=%s",
        snap.id,
        snap.scope_key,
        float(snap.coverage_rate or 0),
        snap.gap_company_count,
        source,
    )
    return snap


def snapshot_to_dict(
    snap: FinancialCoverageSnapshot,
    *,
    include_companies: bool = True,
) -> Dict[str, Any]:
    companies: List[Dict[str, Any]] = []
    if include_companies and snap.companies_payload:
        try:
            companies = json.loads(snap.companies_payload)
        except json.JSONDecodeError:
            companies = []
    return {
        "snapshot_id": snap.id,
        "scope_key": snap.scope_key,
        "years": snap.years or [],
        "report_types": snap.report_types or [],
        "status_filter": snap.status_filter,
        "source": snap.source,
        "trigger_task_id": snap.trigger_task_id,
        "summary": snap.summary or {},
        "gap_companies": snap.gap_companies or [],
        "companies": companies if include_companies else [],
        "core_subjects": snap.core_subjects or core_subjects_payload(snap.report_types or ["BS", "IS", "CF"]),
        "scan_duration_ms": snap.scan_duration_ms or 0,
        "from_snapshot": True,
        "scanned_at": snap.created_at.isoformat() if snap.created_at else None,
        "company_count": snap.company_count,
        "gap_company_count": snap.gap_company_count,
        "coverage_rate": float(snap.coverage_rate or 0),
    }


async def get_latest_snapshot(
    session: AsyncSession,
    *,
    years: Optional[Sequence[int]] = None,
    report_types: Optional[Sequence[str]] = None,
    status_filter: str = "active",
    scope_key: Optional[str] = None,
) -> Optional[FinancialCoverageSnapshot]:
    if not scope_key:
        y = default_coverage_years(years)
        r = normalize_report_types(report_types)
        scope_key = build_scope_key(y, r, status_filter)
    stmt = (
        select(FinancialCoverageSnapshot)
        .where(FinancialCoverageSnapshot.scope_key == scope_key)
        .order_by(FinancialCoverageSnapshot.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_snapshots(
    session: AsyncSession,
    *,
    scope_key: Optional[str] = None,
    limit: int = 20,
) -> List[FinancialCoverageSnapshot]:
    stmt = select(FinancialCoverageSnapshot).order_by(
        FinancialCoverageSnapshot.created_at.desc()
    )
    if scope_key:
        stmt = stmt.where(FinancialCoverageSnapshot.scope_key == scope_key)
    stmt = stmt.limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def scan_and_save(
    session: AsyncSession,
    *,
    years: Optional[Sequence[int]] = None,
    report_types: Optional[Sequence[str]] = None,
    status_filter: str = "active",
    stock_codes: Optional[Sequence[str]] = None,
    search: Optional[str] = None,
    source: str = "manual_scan",
    trigger_task_id: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    """扫描并落库，返回带 snapshot_id 的结果。"""
    result = await scan_coverage(
        session,
        years=years,
        report_types=report_types,
        status_filter=status_filter,
        stock_codes=stock_codes,
        search=search,
    )
    # 限定公司/搜索的局部扫描不覆盖全市场快照 scope
    is_partial_scope = bool(stock_codes) or bool(search)
    if is_partial_scope:
        result["from_snapshot"] = False
        result["snapshot_id"] = None
        result["scanned_at"] = None
        result["partial_scope"] = True
        return result

    snap = await save_coverage_snapshot(
        session,
        result,
        source=source,
        trigger_task_id=trigger_task_id,
        created_by=created_by,
    )
    result["from_snapshot"] = True
    result["snapshot_id"] = snap.id
    result["scanned_at"] = snap.created_at.isoformat() if snap.created_at else None
    result["source"] = source
    result["partial_scope"] = False
    return result


def paginate_coverage_result(
    result: Dict[str, Any],
    *,
    only_gaps: bool = False,
    page: int = 1,
    page_size: int = 50,
    include_cells: bool = True,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """对扫描/快照结果做筛选分页，供 API 返回。"""
    companies = list(result.get("companies") or [])
    if search:
        q = search.strip().lower()
        companies = [
            c
            for c in companies
            if q in str(c.get("stock_code", "")).lower()
            or q in str(c.get("stock_name", "")).lower()
        ]
    if only_gaps:
        companies = [c for c in companies if c.get("overall_status") != "complete"]

    total = len(companies)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    page_items = companies[start:end]
    if not include_cells:
        page_items = [{k: v for k, v in item.items() if k != "cells"} for item in page_items]

    return {
        "years": result.get("years") or [],
        "report_types": result.get("report_types") or [],
        "status_filter": result.get("status_filter") or "active",
        "summary": result.get("summary") or {},
        "gap_companies": result.get("gap_companies") or [],
        "page": page,
        "page_size": page_size,
        "total": total,
        "companies": page_items,
        "core_subjects": result.get("core_subjects") or {},
        "from_snapshot": bool(result.get("from_snapshot")),
        "snapshot_id": result.get("snapshot_id"),
        "scanned_at": result.get("scanned_at"),
        "scan_duration_ms": result.get("scan_duration_ms"),
        "source": result.get("source"),
        "scope_key": result.get("scope_key"),
    }


async def refresh_coverage_after_repair(
    *,
    years: Optional[Sequence[int]] = None,
    report_types: Optional[Sequence[str]] = None,
    status_filter: str = "active",
    trigger_task_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    补采结束后刷新全市场快照（独立 session，避免污染任务事务）。
    """
    from ..persistence.db import async_session_factory

    try:
        async with async_session_factory() as session:
            result = await scan_and_save(
                session,
                years=years,
                report_types=report_types,
                status_filter=status_filter,
                source="post_repair",
                trigger_task_id=trigger_task_id,
            )
            return {
                "snapshot_id": result.get("snapshot_id"),
                "coverage_rate": (result.get("summary") or {}).get("coverage_rate"),
                "gap_company_count": (result.get("summary") or {}).get("gap_company_count"),
                "scan_duration_ms": result.get("scan_duration_ms"),
            }
    except Exception as e:
        logger.error("refresh_coverage_after_repair failed: %s", e, exc_info=True)
        return None
