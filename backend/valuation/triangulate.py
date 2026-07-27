# -*- coding: utf-8 -*-
"""
多方法估值三角验证。

综合 DCF、剩余收益、相对估值，输出加权公允价、分歧度、情景与 headline。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .dcf import DCFValuationService
from .industry_profiles import get_industry_profile, method_weight
from .relative import RelativeValuationService
from .residual_income import ResidualIncomeService
from .scenarios import build_bull_base_bear_prices, rating_from_upside
from .sotp import SOTPValuationService
from .wacc import WACCService

logger = logging.getLogger(__name__)


class TriangulationService:
    """多方法估值综合服务。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def valuate(
        self,
        stock_code: str,
        *,
        dcf_params: Optional[Dict[str, float]] = None,
        ri_params: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        wacc_svc = WACCService(self.session)
        dcf_svc = DCFValuationService(self.session)
        ri_svc = ResidualIncomeService(self.session)
        rel_svc = RelativeValuationService(self.session)

        wacc_info = await wacc_svc.calculate(stock_code)
        industry = wacc_info.get("industry")

        # 用自动 WACC/Ke 填充默认参数（可被覆盖）
        dcf_params = dict(dcf_params or {})
        ri_params = dict(ri_params or {})
        if "discount_rate" not in dcf_params and "wacc" in wacc_info:
            dcf_params["discount_rate"] = wacc_info["wacc"]
        if "tax_rate" not in dcf_params and "tax_rate" in wacc_info:
            dcf_params["tax_rate"] = wacc_info["tax_rate"]
        if "cost_of_equity" not in ri_params and "ke" in wacc_info:
            ri_params["cost_of_equity"] = wacc_info["ke"]

        dcf_result = await dcf_svc.valuate(stock_code, params=dcf_params)
        ri_result = await ri_svc.valuate(stock_code, params=ri_params)
        rel_result = await rel_svc.valuate(stock_code)
        sotp_result = await SOTPValuationService(self.session).valuate(stock_code)

        methods: List[Dict[str, Any]] = []
        methods.append(self._pack_method("DCF", dcf_result))
        methods.append(self._pack_method("RI", ri_result))
        methods.append(self._pack_method("RELATIVE", rel_result))
        methods.append(self._pack_method("SOTP", sotp_result))

        has_dcf = methods[0]["applicable"] and methods[0]["implied_price"] is not None
        has_ri = methods[1]["applicable"] and methods[1]["implied_price"] is not None
        has_rel = methods[2]["applicable"] and methods[2]["implied_price"] is not None
        has_sotp = methods[3]["applicable"] and methods[3]["implied_price"] is not None

        weights = method_weight(
            industry,
            has_dcf=has_dcf,
            has_ri=has_ri,
            has_relative=has_rel,
            has_sotp=has_sotp,
        )

        blended, used = self._blend(methods, weights)
        prices = [m["implied_price"] for m in methods if m.get("implied_price")]
        divergence = None
        if len(prices) >= 2:
            divergence = round((max(prices) - min(prices)) / (sum(prices) / len(prices)) * 100, 2)

        company = (
            dcf_result.get("company")
            or ri_result.get("company")
            or rel_result.get("company")
            or {"stock_code": stock_code}
        )
        current_price = (
            dcf_result.get("current_price")
            or ri_result.get("current_price")
            or rel_result.get("current_price")
            or 0
        )
        current_price = float(current_price or 0)

        upside = None
        if blended and current_price > 0:
            upside = round((blended - current_price) / current_price * 100, 2)

        confidence = "high"
        if divergence is not None and divergence > 30:
            confidence = "low"
        elif divergence is not None and divergence > 15:
            confidence = "medium"
        elif sum(1 for m in methods if m["applicable"]) < 2:
            confidence = "low"
        else:
            confidence = "medium" if not has_dcf or not has_rel else "high"

        rating = rating_from_upside(upside)
        scenarios = build_bull_base_bear_prices(blended or 0) if blended else None

        # DCF 敏感性优先
        sensitivity = None
        if isinstance(dcf_result.get("valuation"), dict):
            sensitivity = dcf_result["valuation"].get("sensitivity")

        risks = self._collect_risks(methods, dcf_result, rel_result, divergence, wacc_info)
        if sotp_result.get("conglomerate_discount_flag"):
            risks.insert(0, f"SOTP 显示集团折扣约 {sotp_result.get('discount_pct')}%")
        headline = self._headline(company, blended, current_price, upside, methods, confidence)

        return {
            "stock_code": stock_code,
            "company": company,
            "current_price": current_price,
            "wacc": wacc_info,
            "methods": methods,
            "weights": weights,
            "weights_used": used,
            "blended_price": round(blended, 4) if blended is not None else None,
            "upside_pct": upside,
            "divergence_pct": divergence,
            "confidence": confidence,
            "scenarios": scenarios,
            "sensitivity": sensitivity,
            "investment_rating": rating,
            "margin_of_safety": self._margin(blended, current_price) if blended else None,
            "headline": headline,
            "risks": risks,
            "industry_profile": get_industry_profile(industry),
            "sotp": sotp_result if sotp_result.get("applicable") else {"applicable": False, "error": sotp_result.get("error")},
            "raw": {
                "dcf_error": dcf_result.get("error"),
                "ri_error": ri_result.get("error"),
                "relative_error": rel_result.get("error"),
                "sotp_error": sotp_result.get("error"),
            },
        }

    def _pack_method(self, name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        if result.get("error") and not (
            isinstance(result.get("valuation"), dict)
            and result["valuation"].get("intrinsic_value_per_share") is not None
        ):
            return {
                "method": name,
                "applicable": False,
                "implied_price": None,
                "confidence": "low",
                "skip_reason": result.get("error"),
                "assumptions": result.get("parameters") or {},
                "details": {},
                "gates": result.get("gates"),
                "investment_rating": result.get("investment_rating"),
                "upside_downside": result.get("upside_downside"),
            }

        valuation = result.get("valuation") or {}
        price = valuation.get("intrinsic_value_per_share")
        if price is None and name == "RELATIVE":
            price = (result.get("valuation") or {}).get("intrinsic_value_per_share")

        applicable = result.get("applicable", price is not None and price > 0)
        if price is not None and price <= 0:
            applicable = False

        conf = result.get("confidence") or ("medium" if applicable else "low")
        return {
            "method": name,
            "applicable": bool(applicable and price is not None),
            "implied_price": round(float(price), 4) if price is not None else None,
            "confidence": conf,
            "skip_reason": None if applicable else result.get("error"),
            "assumptions": result.get("parameters") or result.get("medians") or {},
            "details": {
                "inputs": result.get("inputs"),
                "implied_by_multiple": result.get("implied_by_multiple"),
                "adjustment": result.get("adjustment"),
                "terminal_methods": valuation.get("terminal_methods") if isinstance(valuation, dict) else None,
                "wacc_breakdown": result.get("wacc_breakdown"),
                "peers_count": len(result.get("peers") or []) if name == "RELATIVE" else None,
            },
            "gates": result.get("gates") or (valuation.get("gates") if isinstance(valuation, dict) else None),
            "investment_rating": result.get("investment_rating"),
            "upside_downside": result.get("upside_downside"),
            "full": result if name == "RELATIVE" else None,  # relative 体积可控时保留
        }

    def _blend(
        self,
        methods: List[Dict[str, Any]],
        weights: Dict[str, float],
    ) -> tuple[Optional[float], Dict[str, float]]:
        total_w = 0.0
        acc = 0.0
        used: Dict[str, float] = {}
        for m in methods:
            name = m["method"]
            w = float(weights.get(name, 0.0))
            price = m.get("implied_price")
            if not m.get("applicable") or price is None or w <= 0:
                used[name] = 0.0
                continue
            acc += price * w
            total_w += w
            used[name] = w

        if total_w <= 0:
            # fallback equal
            prices = [m["implied_price"] for m in methods if m.get("implied_price")]
            if not prices:
                return None, used
            eq = 1.0 / len(prices)
            for m in methods:
                if m.get("implied_price"):
                    used[m["method"]] = eq
            return sum(prices) / len(prices), used

        # 归一
        used = {k: round(v / total_w, 4) for k, v in used.items()}
        return acc / total_w, used

    def _collect_risks(
        self,
        methods: List[Dict[str, Any]],
        dcf_result: Dict[str, Any],
        rel_result: Dict[str, Any],
        divergence: Optional[float],
        wacc_info: Dict[str, Any],
    ) -> List[str]:
        risks: List[str] = []
        if divergence is not None and divergence > 30:
            risks.append(f"方法分歧较大（{divergence}%），综合价置信度下降")
        sanity = wacc_info.get("sanity") or {}
        if sanity.get("message"):
            risks.append(sanity["message"])
        gates = []
        if isinstance(dcf_result.get("valuation"), dict):
            gates = dcf_result["valuation"].get("gates") or dcf_result.get("gates") or []
        for g in gates or []:
            if isinstance(g, dict) and not g.get("ok", True):
                risks.append(g.get("message") or g.get("name") or "DCF gate 未通过")
        if dcf_result.get("error"):
            risks.append(f"DCF: {dcf_result['error']}")
        if rel_result.get("error") and not rel_result.get("applicable", True):
            risks.append(f"相对估值: {rel_result['error']}")
        if not risks:
            risks.append("关键假设包括折现率、增长率与同业倍数；结果对假设敏感")
        return risks[:6]

    def _headline(
        self,
        company: Dict[str, Any],
        blended: Optional[float],
        current: float,
        upside: Optional[float],
        methods: List[Dict[str, Any]],
        confidence: str,
    ) -> str:
        name = company.get("stock_name") or company.get("stock_code") or ""
        if blended is None:
            return f"{name} 综合估值数据不足，无法给出公允价"
        side = "上涨" if (upside or 0) >= 0 else "下跌"
        ups = f"{abs(upside):.1f}%" if upside is not None else "N/A"
        parts = []
        for m in methods:
            if m.get("implied_price") is not None and m.get("applicable"):
                parts.append(f"{m['method']} ¥{m['implied_price']:.2f}")
        methods_txt = "；".join(parts) if parts else "无可用分项"
        conf_cn = {"high": "高", "medium": "中", "low": "低"}.get(confidence, confidence)
        vs = f"现价 ¥{current:.2f}，潜在{side} {ups}" if current > 0 else "现价不可用"
        return (
            f"{name} 综合公允价约 ¥{blended:.2f}（{vs}；置信度{conf_cn}）。"
            f"分项：{methods_txt}。"
        )

    @staticmethod
    def _margin(intrinsic: Optional[float], price: float) -> Dict[str, Any]:
        if not intrinsic or price <= 0:
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
