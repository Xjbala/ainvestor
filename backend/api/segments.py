# -*- coding: utf-8 -*-
"""
公司分部（主营构成）API

供 SOTP 与专家模式使用：查询、手工录入、从年报 Markdown 抽取。
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..persistence.db import get_db_session
from ..persistence.financial_models import QualitativeReport
from ..persistence.segment_repository import SegmentRepository
from ..crawler.qualitative.segment_extractor import SegmentExtractor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/segments", tags=["分部数据"])


class SegmentItem(BaseModel):
    segment_name: str
    segment_type: str = "product"
    revenue: Optional[float] = None
    operating_income: Optional[float] = None
    ebitda: Optional[float] = None
    revenue_yoy: Optional[float] = None
    op_margin: Optional[float] = None
    currency: str = "CNY"
    source: str = "manual"
    source_url: Optional[str] = None
    confidence: str = "medium"
    raw_snippet: Optional[str] = None
    multiple_override: Optional[float] = None
    multiple_type: Optional[str] = None
    report_type: str = "annual"


class SegmentBulkRequest(BaseModel):
    company_code: str
    report_period: date
    report_type: str = "annual"
    source: str = "manual"
    source_url: Optional[str] = None
    confidence: str = "high"
    segments: List[SegmentItem]


class SegmentResponse(BaseModel):
    id: Optional[int] = None
    company_code: str
    report_period: Optional[str] = None
    report_type: Optional[str] = None
    segment_name: str
    segment_type: str
    revenue: Optional[float] = None
    operating_income: Optional[float] = None
    ebitda: Optional[float] = None
    revenue_yoy: Optional[float] = None
    op_margin: Optional[float] = None
    currency: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    confidence: Optional[str] = None
    multiple_override: Optional[float] = None
    multiple_type: Optional[str] = None


class ExtractRequest(BaseModel):
    use_llm_fallback: bool = True
    persist: bool = True


@router.get("/{stock_code}", response_model=List[SegmentResponse])
async def list_segments(
    stock_code: str,
    latest_only: bool = Query(True, description="仅返回最近一期"),
    report_period: Optional[date] = Query(None),
    session: AsyncSession = Depends(get_db_session),
):
    """查询公司分部数据。"""
    repo = SegmentRepository(session)
    rows = await repo.list_by_company(
        stock_code,
        report_period=report_period,
        latest_only=latest_only and report_period is None,
    )
    return [SegmentResponse(**SegmentRepository.to_dict(r)) for r in rows]


@router.post("/bulk", response_model=List[SegmentResponse])
async def bulk_upsert_segments(
    body: SegmentBulkRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """批量写入/替换某报告期分部（手工或外部导入）。"""
    if not body.segments:
        raise HTTPException(status_code=400, detail="segments 不能为空")
    repo = SegmentRepository(session)
    rows = await repo.replace_period_segments(
        body.company_code,
        body.report_period,
        [s.model_dump() for s in body.segments],
        report_type=body.report_type,
        source=body.source,
        source_url=body.source_url,
        confidence=body.confidence,
    )
    return [SegmentResponse(**SegmentRepository.to_dict(r)) for r in rows]


@router.post("/{stock_code}/extract")
async def extract_segments_from_qualitative(
    stock_code: str,
    body: ExtractRequest = ExtractRequest(),
    session: AsyncSession = Depends(get_db_session),
):
    """
    从已采集的年报 Markdown（qualitative_reports）抽取分部并可选入库。
    """
    stmt = (
        select(QualitativeReport)
        .where(QualitativeReport.company_code == stock_code)
        .order_by(QualitativeReport.report_period.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    report = result.scalar_one_or_none()
    if not report or not report.management_discussion:
        raise HTTPException(
            status_code=404,
            detail=f"未找到 {stock_code} 的年报 Markdown，请先跑定性采集任务",
        )

    extractor = SegmentExtractor()
    extracted = extractor.extract(
        report.management_discussion,
        company_code=stock_code,
        report_period=report.report_period,
        use_llm_fallback=body.use_llm_fallback,
    )

    saved: List[Dict[str, Any]] = []
    if body.persist and extracted.get("segments"):
        repo = SegmentRepository(session)
        rows = await repo.replace_period_segments(
            stock_code,
            report.report_period,
            extracted["segments"],
            report_type=report.report_type or "annual",
            source=extracted.get("source") or "cninfo_pdf",
            source_url=report.source_url,
            confidence=extracted.get("confidence") or "medium",
        )
        saved = [SegmentRepository.to_dict(r) for r in rows]

    return {
        "stock_code": stock_code,
        "report_period": report.report_period.isoformat() if report.report_period else None,
        "extracted": extracted,
        "saved_count": len(saved),
        "saved": saved,
    }


@router.delete("/{stock_code}")
async def delete_segments(
    stock_code: str,
    report_period: Optional[date] = Query(None),
    session: AsyncSession = Depends(get_db_session),
):
    """删除分部数据（可选按报告期）。"""
    from sqlalchemy import delete
    from ..persistence.financial_models import CompanySegment

    stmt = delete(CompanySegment).where(CompanySegment.company_code == stock_code)
    if report_period:
        stmt = stmt.where(CompanySegment.report_period == report_period)
    result = await session.execute(stmt)
    await session.commit()
    return {"deleted": result.rowcount or 0}
