# -*- coding: utf-8 -*-
"""
相对估值（Peer Multiple）服务。

使用同行业 A 股 peer 的 PE / PB / 近似 EV 倍数中位数推断隐含股价。
"""

from __future__ import annotations

import logging
from statistics import median
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..persistence.financial_models import Company, CompanyStatus, FinancialData, ReportType
from .industry_profiles import get_industry_profile
from .scenarios import build_bull_base_bear_prices, rating_from_upside

logger = logging.getLogger(__name__)


class RelativeValuationService:
    """同业相对估值。"""

    SUBJECT = {
        "net_income": (["ISF021"], ReportType.IS),
        "revenue": (["ISI001"], ReportType.IS),
        "operating_income": (["ISF016"], ReportType.IS),
        "equity": (["BSE010"], ReportType.BS),
        "shares": (["BSE001"], ReportType.BS),
        "total_assets": (["BSA121"], ReportType.BS),
        "total_liab": (["BSL112"], ReportType.BS),
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def valuate(
        self,
        stock_code: str,
        peer_codes: Optional[Sequence[str]] = None,
        max_peers: int = 8,
    ) -> Dict[str, Any]:
        company = await self._get_company(stock_code)
        if not company:
            return {"error": f"公司不存在: {stock_code}"}

        industry_name = company.industry.name if company.industry else None
        profile = get_industry_profile(industry_name)

        target_fin = await self._get_financials(stock_code)
        if not target_fin:
            return {
                "company": self._company_dict(company),
                "error": "无法获取目标公司财务数据",
            }

        peers = await self._select_peers(company, peer_codes=peer_codes, max_peers=max_peers)
        if len(peers) < 3:
            return {
                "company": self._company_dict(company),
                "method": "Relative (Peer Multiple)",
                "applicable": False,
                "error": f"同业样本不足（{len(peers)} 家，至少需要 3 家）",
                "peers": peers,
                "industry": industry_name,
                "profile_key": profile.get("profile_key"),
            }

        peer_rows: List[Dict[str, Any]] = []
        for p in peers:
            fin = await self._get_financials(p["stock_code"])
            if not fin:
                continue
            row = self._peer_metrics(p, fin)
            if row:
                peer_rows.append(row)

        if len(peer_rows) < 3:
            return {
                "company": self._company_dict(company),
                "method": "Relative (Peer Multiple)",
                "applicable": False,
                "error": "有效同业倍数不足 3 个",
                "peers": peer_rows,
            }

        med_pe = self._nanmedian([r.get("pe") for r in peer_rows])
        med_pb = self._nanmedian([r.get("pb") for r in peer_rows])
        med_ps = self._nanmedian([r.get("ps") for r in peer_rows])

        target_metrics = self._peer_metrics(self._company_dict(company), target_fin)
        target_eps = target_fin["net_income"] / target_fin["shares"] if target_fin["shares"] else None
        target_bps = target_fin["equity"] / target_fin["shares"] if target_fin["shares"] else None
        target_sps = target_fin["revenue"] / target_fin["shares"] if target_fin["shares"] else None

        # 相对调整
        adj, adj_reasons = self._adjustment(target_metrics, peer_rows)

        implied: Dict[str, Optional[float]] = {}
        if med_pe and target_eps and target_eps > 0:
            implied["pe"] = med_pe * (1 + adj) * target_eps
        if med_pb and target_bps and target_bps > 0:
            implied["pb"] = med_pb * (1 + adj) * target_bps
        if med_ps and target_sps and target_sps > 0:
            implied["ps"] = med_ps * (1 + adj) * target_sps

        primary = profile.get("relative_primary") or "pe"
        # 银行/保险优先 PB
        ordered = []
        if primary == "pb":
            ordered = ["pb", "pe", "ps"]
        elif primary == "ev_sales" or primary == "ps":
            ordered = ["ps", "pe", "pb"]
        else:
            ordered = ["pe", "pb", "ps"]

        prices = [implied[k] for k in ordered if implied.get(k)]
        if not prices:
            # 任意可用
            prices = [v for v in implied.values() if v and v > 0]

        if not prices:
            return {
                "company": self._company_dict(company),
                "method": "Relative (Peer Multiple)",
                "applicable": False,
                "error": "无法计算隐含价格（盈利/净资产/营收数据不足）",
                "peers": peer_rows,
                "medians": {"pe": med_pe, "pb": med_pb, "ps": med_ps},
            }

        implied_price = float(median(prices))
        current_price = float(company.current_price or 0)
        upside = None
        if current_price > 0:
            upside = round((implied_price - current_price) / current_price * 100, 2)

        rating = rating_from_upside(upside)
        scenarios = build_bull_base_bear_prices(implied_price)

        return {
            "company": self._company_dict(company),
            "method": "Relative (Peer Multiple)",
            "applicable": True,
            "industry": industry_name,
            "profile_key": profile.get("profile_key"),
            "primary_multiple": primary,
            "adjustment": {
                "factor": round(adj, 4),
                "reasons": adj_reasons,
            },
            "medians": {
                "pe": med_pe,
                "pb": med_pb,
                "ps": med_ps,
            },
            "implied_by_multiple": {k: round(v, 4) if v else None for k, v in implied.items()},
            "valuation": {
                "intrinsic_value_per_share": round(implied_price, 4),
                "scenarios": {
                    "conservative": {
                        "valuation": scenarios["bear"]["price"],
                        "upside_downside": self._upside(scenarios["bear"]["price"], current_price),
                        "rating": rating_from_upside(self._upside(scenarios["bear"]["price"], current_price)),
                        "terminal_assumption": "Bear multiple stress",
                    },
                    "base": {
                        "valuation": scenarios["base"]["price"],
                        "upside_downside": upside,
                        "rating": rating,
                        "terminal_assumption": "Peer median + adjustment",
                    },
                    "optimistic": {
                        "valuation": scenarios["bull"]["price"],
                        "upside_downside": self._upside(scenarios["bull"]["price"], current_price),
                        "rating": rating_from_upside(self._upside(scenarios["bull"]["price"], current_price)),
                        "terminal_assumption": "Bull multiple expansion",
                    },
                },
            },
            "peers": peer_rows,
            "target_metrics": target_metrics,
            "current_price": current_price,
            "upside_downside": upside,
            "investment_rating": rating,
            "margin_of_safety": self._margin(implied_price, current_price),
            "confidence": "medium" if len(peer_rows) >= 5 else "low",
        }

    async def _select_peers(
        self,
        company: Company,
        peer_codes: Optional[Sequence[str]],
        max_peers: int,
    ) -> List[Dict[str, Any]]:
        if peer_codes:
            rows = []
            for code in peer_codes:
                if code == company.stock_code:
                    continue
                c = await self._get_company(code)
                if c and not c.is_st:
                    rows.append(self._company_dict(c))
            return rows[:max_peers]

        if not company.industry_id:
            return []

        stmt = (
            select(Company)
            .options(selectinload(Company.industry))
            .where(
                Company.industry_id == company.industry_id,
                Company.stock_code != company.stock_code,
                Company.status == CompanyStatus.ACTIVE,
                Company.is_st.is_(False),
            )
            .limit(40)
        )
        result = await self.session.execute(stmt)
        candidates = list(result.scalars().all())

        # 市值接近优先
        target_mc = float(company.market_cap or 0)

        def sort_key(c: Company):
            mc = float(c.market_cap or 0)
            if target_mc > 0 and mc > 0:
                return abs(mc - target_mc)
            return 1e18

        candidates.sort(key=sort_key)
        return [self._company_dict(c) for c in candidates[:max_peers]]

    async def _get_company(self, stock_code: str) -> Optional[Company]:
        result = await self.session.execute(
            select(Company)
            .options(selectinload(Company.industry))
            .where(Company.stock_code == stock_code)
        )
        return result.scalars().first()

    async def _get_financials(self, stock_code: str) -> Optional[Dict[str, float]]:
        year = await self._latest_year(stock_code)
        if not year:
            return None
        data: Dict[str, float] = {}
        for field, (codes, rtype) in self.SUBJECT.items():
            val = 0.0
            for code in codes:
                stmt = (
                    select(FinancialData.value_decimal)
                    .where(
                        FinancialData.company_code == stock_code,
                        FinancialData.subject_code == code,
                        func.extract("year", FinancialData.report_date) == year,
                        FinancialData.report_type == rtype,
                    )
                    .order_by(FinancialData.report_date.desc())
                    .limit(1)
                )
                result = await self.session.execute(stmt)
                v = result.scalar()
                if v is not None:
                    val = float(v)
                    break
            data[field] = val

        if data.get("shares", 0) <= 0:
            company = await self._get_company(stock_code)
            if company and company.total_shares:
                data["shares"] = float(company.total_shares)

        if data.get("shares", 0) <= 0:
            return None
        return data

    async def _latest_year(self, stock_code: str) -> Optional[int]:
        stmt = (
            select(FinancialData.report_date)
            .where(
                FinancialData.company_code == stock_code,
                FinancialData.report_type == ReportType.IS,
            )
            .order_by(FinancialData.report_date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        d = result.scalar()
        if not d:
            return None
        return d.year if hasattr(d, "year") else int(str(d)[:4])

    def _peer_metrics(self, company: Dict[str, Any], fin: Dict[str, float]) -> Optional[Dict[str, Any]]:
        shares = fin.get("shares") or 0
        if shares <= 0:
            return None
        price = float(company.get("current_price") or 0)
        # 若无现价，用库内 pe/pb 回推
        pe_db = company.get("pe_ratio")
        pb_db = company.get("pb_ratio")
        eps = fin["net_income"] / shares if shares else None
        bps = fin["equity"] / shares if shares else None
        sps = fin["revenue"] / shares if shares else None

        pe = None
        pb = None
        ps = None
        if price > 0 and eps and eps > 0:
            pe = price / eps
        elif pe_db and float(pe_db) > 0:
            pe = float(pe_db)
        if price > 0 and bps and bps > 0:
            pb = price / bps
        elif pb_db and float(pb_db) > 0:
            pb = float(pb_db)
        if price > 0 and sps and sps > 0:
            ps = price / sps

        # 过滤极端值
        if pe is not None and (pe <= 0 or pe > 150):
            pe = None
        if pb is not None and (pb <= 0 or pb > 30):
            pb = None
        if ps is not None and (ps <= 0 or ps > 50):
            ps = None

        roe = None
        if bps and bps > 0 and eps is not None:
            roe = eps / bps

        return {
            "stock_code": company.get("stock_code"),
            "stock_name": company.get("stock_name"),
            "current_price": price,
            "pe": round(pe, 2) if pe else None,
            "pb": round(pb, 2) if pb else None,
            "ps": round(ps, 2) if ps else None,
            "roe": round(roe, 4) if roe is not None else None,
            "eps": round(eps, 4) if eps is not None else None,
            "bps": round(bps, 4) if bps is not None else None,
            "market_cap": company.get("market_cap"),
        }

    def _adjustment(
        self,
        target: Optional[Dict[str, Any]],
        peers: List[Dict[str, Any]],
    ) -> tuple[float, List[str]]:
        if not target:
            return 0.0, []
        reasons: List[str] = []
        adj = 0.0

        peer_roes = [p["roe"] for p in peers if p.get("roe") is not None]
        if target.get("roe") is not None and peer_roes:
            med_roe = median(peer_roes)
            diff = target["roe"] - med_roe
            if diff > 0.03:
                adj += 0.10
                reasons.append(f"ROE 高于同业中位 {diff:.1%}，倍数 +10%")
            elif diff < -0.03:
                adj -= 0.10
                reasons.append(f"ROE 低于同业中位 {abs(diff):.1%}，倍数 -10%")

        # 估值已高/低不在这里再叠调整，避免循环
        adj = max(-0.25, min(0.25, adj))
        if not reasons:
            reasons.append("与同业质量接近，使用中位数倍数")
        return adj, reasons

    @staticmethod
    def _nanmedian(values: List[Optional[float]]) -> Optional[float]:
        clean = [float(v) for v in values if v is not None]
        if not clean:
            return None
        return float(median(clean))

    @staticmethod
    def _upside(price: float, current: float) -> Optional[float]:
        if current <= 0:
            return None
        return round((price - current) / current * 100, 2)

    @staticmethod
    def _margin(intrinsic: float, price: float) -> Dict[str, Any]:
        if price <= 0 or intrinsic <= 0:
            return {
                "margin_percent": 0.0,
                "diff": 0.0,
                "status": "unknown",
                "recommendation": "无法计算安全边际",
            }
        margin = (intrinsic - price) / intrinsic
        if margin > 0.3:
            status, rec = "undervalued", "具有较高安全边际，可考虑买入"
        elif margin > 0.1:
            status, rec = "fairly_valued", "估值合理，可持有观望"
        else:
            status, rec = "overvalued", "当前价格较高，注意风险"
        return {
            "margin_percent": round(margin * 100, 2),
            "diff": round(intrinsic - price, 2),
            "status": status,
            "recommendation": rec,
        }

    @staticmethod
    def _company_dict(company: Any) -> Dict[str, Any]:
        if isinstance(company, dict):
            return company
        return {
            "stock_code": company.stock_code,
            "stock_name": company.stock_name,
            "company_name": company.company_name,
            "industry": company.industry.name if company.industry else None,
            "current_price": float(company.current_price) if company.current_price else None,
            "market_cap": float(company.market_cap) if company.market_cap else None,
            "pe_ratio": float(company.pe_ratio) if company.pe_ratio else None,
            "pb_ratio": float(company.pb_ratio) if company.pb_ratio else None,
        }
