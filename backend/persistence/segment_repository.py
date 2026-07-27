# -*- coding: utf-8 -*-
"""公司分部数据仓库"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .financial_models import CompanySegment


def _dec(v: Optional[float]) -> Optional[Decimal]:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


class SegmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_company(
        self,
        company_code: str,
        *,
        report_period: Optional[date] = None,
        latest_only: bool = False,
    ) -> List[CompanySegment]:
        stmt = select(CompanySegment).where(CompanySegment.company_code == company_code)
        if report_period:
            stmt = stmt.where(CompanySegment.report_period == report_period)
        stmt = stmt.order_by(
            CompanySegment.report_period.desc(),
            CompanySegment.segment_type,
            CompanySegment.segment_name,
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if latest_only and rows:
            latest = rows[0].report_period
            rows = [r for r in rows if r.report_period == latest]
        return rows

    async def get_latest_period(self, company_code: str) -> Optional[date]:
        stmt = (
            select(CompanySegment.report_period)
            .where(CompanySegment.company_code == company_code)
            .order_by(CompanySegment.report_period.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar()

    async def replace_period_segments(
        self,
        company_code: str,
        report_period: date,
        segments: Sequence[Dict[str, Any]],
        *,
        report_type: str = "annual",
        source: str = "manual",
        source_url: Optional[str] = None,
        confidence: str = "medium",
    ) -> List[CompanySegment]:
        """替换某报告期的全部分部（同 source 或全量，这里全量替换该期）。"""
        await self.session.execute(
            delete(CompanySegment).where(
                CompanySegment.company_code == company_code,
                CompanySegment.report_period == report_period,
            )
        )
        created: List[CompanySegment] = []
        for seg in segments:
            name = (seg.get("segment_name") or seg.get("name") or "").strip()
            if not name:
                continue
            rev = seg.get("revenue")
            opi = seg.get("operating_income")
            ebitda = seg.get("ebitda")
            margin = None
            if rev and opi and float(rev) != 0:
                try:
                    margin = float(opi) / float(rev)
                except Exception:
                    margin = None
            row = CompanySegment(
                company_code=company_code,
                report_period=report_period,
                report_type=seg.get("report_type") or report_type,
                segment_name=name[:100],
                segment_type=seg.get("segment_type") or "product",
                revenue=_dec(rev if rev is None else float(rev)),
                operating_income=_dec(opi if opi is None else float(opi)),
                ebitda=_dec(ebitda if ebitda is None else float(ebitda)),
                revenue_yoy=_dec(seg.get("revenue_yoy")),
                op_margin=_dec(margin if margin is not None else seg.get("op_margin")),
                currency=seg.get("currency") or "CNY",
                source=seg.get("source") or source,
                source_url=seg.get("source_url") or source_url,
                confidence=seg.get("confidence") or confidence,
                raw_snippet=(seg.get("raw_snippet") or "")[:2000] or None,
                multiple_override=_dec(seg.get("multiple_override") or seg.get("multiple")),
                multiple_type=seg.get("multiple_type"),
            )
            self.session.add(row)
            created.append(row)
        await self.session.commit()
        for r in created:
            await self.session.refresh(r)
        return created

    async def upsert_one(self, data: Dict[str, Any]) -> CompanySegment:
        company_code = data["company_code"]
        report_period = data["report_period"]
        if isinstance(report_period, str):
            report_period = date.fromisoformat(report_period[:10])
        name = data["segment_name"]
        seg_type = data.get("segment_type") or "product"

        stmt = select(CompanySegment).where(
            CompanySegment.company_code == company_code,
            CompanySegment.report_period == report_period,
            CompanySegment.segment_name == name,
            CompanySegment.segment_type == seg_type,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            row = CompanySegment(
                company_code=company_code,
                report_period=report_period,
                segment_name=name,
                segment_type=seg_type,
            )
            self.session.add(row)

        for field in (
            "report_type",
            "currency",
            "source",
            "source_url",
            "confidence",
            "raw_snippet",
            "multiple_type",
        ):
            if field in data and data[field] is not None:
                setattr(row, field, data[field])
        for field in ("revenue", "operating_income", "ebitda", "revenue_yoy", "op_margin", "multiple_override"):
            if field in data:
                setattr(row, field, _dec(data[field] if data[field] is None else float(data[field])))

        await self.session.commit()
        await self.session.refresh(row)
        return row

    @staticmethod
    def to_dict(row: CompanySegment) -> Dict[str, Any]:
        return {
            "id": row.id,
            "company_code": row.company_code,
            "report_period": row.report_period.isoformat() if row.report_period else None,
            "report_type": row.report_type,
            "segment_name": row.segment_name,
            "segment_type": row.segment_type,
            "revenue": float(row.revenue) if row.revenue is not None else None,
            "operating_income": float(row.operating_income) if row.operating_income is not None else None,
            "ebitda": float(row.ebitda) if row.ebitda is not None else None,
            "revenue_yoy": float(row.revenue_yoy) if row.revenue_yoy is not None else None,
            "op_margin": float(row.op_margin) if row.op_margin is not None else None,
            "currency": row.currency,
            "source": row.source,
            "source_url": row.source_url,
            "confidence": row.confidence,
            "multiple_override": float(row.multiple_override) if row.multiple_override is not None else None,
            "multiple_type": row.multiple_type,
        }

    def to_sotp_segments(
        self,
        rows: Sequence[CompanySegment],
        default_multiple: float = 12.0,
    ) -> List[Dict[str, Any]]:
        segs = []
        for r in rows:
            ebitda = float(r.ebitda) if r.ebitda is not None else None
            if ebitda is None and r.operating_income is not None:
                ebitda = float(r.operating_income)
            mult = float(r.multiple_override) if r.multiple_override is not None else default_multiple
            mtype = r.multiple_type or ("ev_ebitda" if ebitda else "ev_revenue")
            segs.append({
                "name": r.segment_name,
                "revenue": float(r.revenue) if r.revenue is not None else 0.0,
                "ebitda": ebitda or 0.0,
                "operating_income": float(r.operating_income) if r.operating_income is not None else None,
                "multiple": mult,
                "multiple_type": mtype,
            })
        return segs
