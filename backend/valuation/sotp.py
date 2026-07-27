# -*- coding: utf-8 -*-
"""
分部加总（SOTP）估值服务。

无分部数据时返回 applicable=False；支持外部传入 segments 计算。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..persistence.financial_models import Company
from .scenarios import build_bull_base_bear_prices, rating_from_upside

logger = logging.getLogger(__name__)


class SOTPValuationService:
    """
    Sum-of-the-Parts 估值。

    segments 项示例:
    {
      "name": "云业务",
      "ebitda": 1e9,
      "revenue": 5e9,
      "multiple": 18.0,          # EV/EBITDA 或 EV/Rev
      "multiple_type": "ev_ebitda"  # 或 "ev_revenue"
    }
    """

    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session

    async def valuate(
        self,
        stock_code: str,
        segments: Optional[Sequence[Dict[str, Any]]] = None,
        *,
        net_debt: Optional[float] = None,
        cash: Optional[float] = None,
        shares: Optional[float] = None,
        corporate_cost: float = 0.0,
        current_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        company = None
        if self.session is not None:
            company = await self._get_company(stock_code)

        # 未传入 segments 时，从 company_segments 表读取最近一期
        db_meta: Dict[str, Any] = {}
        if not segments and self.session is not None:
            segments, db_meta = await self._load_segments_from_db(stock_code)

        if not segments or len(list(segments)) < 2:
            return {
                "company": self._company_dict(company, stock_code),
                "method": "SOTP (Sum of the Parts)",
                "applicable": False,
                "error": "无分部财务数据（需 ≥2 个分部）；请采集年报并抽取，或 POST /api/segments/bulk 导入",
                "segments": list(segments) if segments else [],
                **db_meta,
            }

        price = current_price
        if price is None and company and company.current_price is not None:
            price = float(company.current_price)

        sh = shares
        if sh is None and company and company.total_shares:
            sh = float(company.total_shares)

        nd = net_debt
        ca = cash
        if self.session is not None and (nd is None or ca is None):
            debt_cash = await self._get_net_debt_cash(stock_code)
            if nd is None:
                nd = debt_cash.get("net_debt", 0.0)
            if ca is None:
                ca = debt_cash.get("cash", 0.0)
        nd = nd if nd is not None else 0.0
        ca = ca if ca is not None else 0.0

        # 未分配总部费用：默认取分部营收合计的 3%（可覆盖）
        if corporate_cost <= 0:
            rev_sum = sum(float(s.get("revenue") or 0) for s in segments)
            if rev_sum > 0:
                corporate_cost = rev_sum * 0.03

        result = self.valuate_from_segments(
            list(segments),
            net_debt=nd,
            cash=ca,
            shares=sh or 0.0,
            current_price=price or 0.0,
            corporate_cost=corporate_cost,
        )
        result["company"] = self._company_dict(company, stock_code)
        result["stock_code"] = stock_code
        result.update(db_meta)
        return result

    async def _load_segments_from_db(
        self, stock_code: str
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        try:
            from ..persistence.segment_repository import SegmentRepository
            from .industry_profiles import get_industry_profile

            repo = SegmentRepository(self.session)
            rows = await repo.list_by_company(stock_code, latest_only=True)
            if not rows:
                return [], {}

            industry = None
            company = await self._get_company(stock_code)
            if company and company.industry:
                industry = company.industry.name
            profile = get_industry_profile(industry)
            default_mult = float(profile.get("exit_ev_ebitda") or 12.0)

            segs = repo.to_sotp_segments(rows, default_multiple=default_mult)
            meta = {
                "report_period": rows[0].report_period.isoformat() if rows[0].report_period else None,
                "segment_source": rows[0].source,
                "segment_confidence": rows[0].confidence,
                "db_segment_count": len(rows),
            }
            return segs, meta
        except Exception as e:
            logger.warning(f"load segments from db failed for {stock_code}: {e}")
            return [], {}

    async def _get_net_debt_cash(self, stock_code: str) -> Dict[str, float]:
        """尽量复用 WACC 服务的债务/现金口径。"""
        try:
            from .wacc import WACCService
            w = await WACCService(self.session).calculate(stock_code)
            return {
                "net_debt": float(w.get("net_debt") or 0),
                "cash": float(w.get("cash") or 0),
                "total_debt": float(w.get("total_debt") or 0),
            }
        except Exception:
            return {"net_debt": 0.0, "cash": 0.0, "total_debt": 0.0}

    @staticmethod
    def valuate_from_segments(
        segments: List[Dict[str, Any]],
        *,
        net_debt: float = 0.0,
        cash: float = 0.0,
        shares: float = 0.0,
        current_price: float = 0.0,
        corporate_cost: float = 0.0,
    ) -> Dict[str, Any]:
        if not segments:
            return {
                "method": "SOTP (Sum of the Parts)",
                "applicable": False,
                "error": "segments 为空",
                "segments": [],
            }

        segment_rows: List[Dict[str, Any]] = []
        total_ev = 0.0
        for seg in segments:
            name = seg.get("name") or "segment"
            mtype = (seg.get("multiple_type") or "ev_ebitda").lower()
            multiple = float(seg.get("multiple") or 0)
            if mtype in ("ev_revenue", "ev_rev", "ev/sales", "ev_sales"):
                base = float(seg.get("revenue") or 0)
                metric = "revenue"
            else:
                base = float(seg.get("ebitda") or seg.get("operating_income") or 0)
                metric = "ebitda"
            ev = base * multiple
            total_ev += ev
            segment_rows.append({
                "name": name,
                "metric": metric,
                "base": base,
                "multiple": multiple,
                "multiple_type": mtype,
                "enterprise_value": round(ev, 2),
            })

        equity = total_ev - corporate_cost - net_debt + cash
        if shares <= 0:
            return {
                "method": "SOTP (Sum of the Parts)",
                "applicable": False,
                "error": "缺少总股本，无法计算每股价值",
                "segments": segment_rows,
                "total_segment_ev": round(total_ev, 2),
            }

        per_share = equity / shares
        upside = None
        if current_price and current_price > 0:
            upside = round((per_share - current_price) / current_price * 100, 2)

        discount_pct = None
        if current_price and current_price > 0 and per_share > 0:
            # (SOTP - market) / SOTP
            discount_pct = round((per_share - current_price) / per_share * 100, 2)

        rating = rating_from_upside(upside)
        scenarios = build_bull_base_bear_prices(per_share)

        conglomerate_flag = discount_pct is not None and discount_pct > 20

        return {
            "method": "SOTP (Sum of the Parts)",
            "applicable": True,
            "segments": segment_rows,
            "adjustments": {
                "corporate_cost": corporate_cost,
                "net_debt": net_debt,
                "cash": cash,
            },
            "total_segment_ev": round(total_ev, 2),
            "equity_value": round(equity, 2),
            "shares": shares,
            "valuation": {
                "intrinsic_value_per_share": round(per_share, 4),
                "scenarios": {
                    "conservative": {
                        "valuation": scenarios["bear"]["price"],
                        "upside_downside": None,
                        "rating": None,
                        "terminal_assumption": "Bear SOTP stress",
                    },
                    "base": {
                        "valuation": scenarios["base"]["price"],
                        "upside_downside": upside,
                        "rating": rating,
                        "terminal_assumption": "Segment peer multiples",
                    },
                    "optimistic": {
                        "valuation": scenarios["bull"]["price"],
                        "upside_downside": None,
                        "rating": None,
                        "terminal_assumption": "Bull SOTP expansion",
                    },
                },
            },
            "current_price": current_price,
            "upside_downside": upside,
            "discount_pct": discount_pct,
            "conglomerate_discount_flag": conglomerate_flag,
            "investment_rating": rating,
            "confidence": "medium" if len(segment_rows) >= 2 else "low",
            "notes": [
                "SOTP 依赖分部数据与 pure-play 倍数假设",
                "折扣持续存在需催化剂（分拆/战略复盘等）",
            ] + (
                [f"检测到集团折扣约 {discount_pct}%，关注价值实现路径"]
                if conglomerate_flag else []
            ),
        }

    async def _get_company(self, stock_code: str) -> Optional[Company]:
        if self.session is None:
            return None
        result = await self.session.execute(
            select(Company)
            .options(selectinload(Company.industry))
            .where(Company.stock_code == stock_code)
        )
        return result.scalars().first()

    @staticmethod
    def _company_dict(company: Optional[Company], stock_code: str) -> Dict[str, Any]:
        if not company:
            return {"stock_code": stock_code}
        return {
            "stock_code": company.stock_code,
            "stock_name": company.stock_name,
            "company_name": company.company_name,
            "industry": company.industry.name if company.industry else None,
            "current_price": float(company.current_price) if company.current_price else None,
        }
