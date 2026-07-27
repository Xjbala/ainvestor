# -*- coding: utf-8 -*-
"""
情景分析与敏感性矩阵工具。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Sequence


def build_sensitivity_grid(
    *,
    base_wacc: float,
    base_g: float,
    last_fcf: float,
    pv_projected_fcf: float,
    net_debt: float,
    shares: float,
    projection_years: int = 5,
    cash: float = 0.0,
    wacc_deltas: Optional[Sequence[float]] = None,
    g_values: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """
    5×5 WACC × g 敏感性矩阵（Gordon 终值）。
    投影期现值固定，仅终值随 WACC/g 变化。
    """
    if wacc_deltas is None:
        wacc_deltas = (-0.01, -0.005, 0.0, 0.005, 0.01)
    if g_values is None:
        g_values = (0.015, 0.020, 0.025, 0.030, 0.035)

    wacc_axis = [round(base_wacc + d, 6) for d in wacc_deltas]
    g_axis = [round(g, 6) for g in g_values]
    grid: List[List[Optional[float]]] = []

    for w in wacc_axis:
        row: List[Optional[float]] = []
        for g in g_axis:
            if w <= g + 0.001 or shares <= 0:
                row.append(None)
                continue
            tv = last_fcf * (1 + g) / (w - g)
            pv_tv = tv / ((1 + w) ** projection_years)
            ev = pv_projected_fcf + pv_tv
            equity = ev + cash - net_debt
            row.append(round(equity / shares, 4))
        grid.append(row)

    return {
        "wacc_axis": wacc_axis,
        "g_axis": g_axis,
        "grid": grid,
        "base_wacc": base_wacc,
        "base_g": base_g,
        "method": "gordon_terminal_only",
    }


def build_bull_base_bear_prices(
    base_price: float,
    *,
    bull_mult: float = 1.18,
    bear_mult: float = 0.82,
) -> Dict[str, Any]:
    """在无法完整重算时的轻量情景（用于相对估值等）。"""
    return {
        "bull": {
            "price": round(base_price * bull_mult, 4),
            "levers": {"multiple_adj": "+18%", "growth": "+300bp", "wacc": "-100bp"},
        },
        "base": {
            "price": round(base_price, 4),
            "levers": {"multiple_adj": "0", "growth": "0", "wacc": "0"},
        },
        "bear": {
            "price": round(base_price * bear_mult, 4),
            "levers": {"multiple_adj": "-18%", "growth": "-300bp", "wacc": "+100bp"},
        },
    }


def dcf_scenario_prices_from_terminal_g(
    *,
    projected_fcf: Sequence[float],
    discount_rate: float,
    net_debt: float,
    shares: float,
    projection_years: int,
    terminal_gs: Dict[str, float],
) -> Dict[str, Any]:
    """按不同永续增长率生成情景估值。"""
    if shares <= 0 or not projected_fcf:
        return {}

    pv_proj = sum(
        f / ((1 + discount_rate) ** (i + 1)) for i, f in enumerate(projected_fcf)
    )
    last = projected_fcf[-1]
    out: Dict[str, Any] = {}
    for name, g in terminal_gs.items():
        denom = discount_rate - g
        if denom <= 0.001:
            denom = 0.001
        tv = last * (1 + g) / denom
        pv_tv = tv / ((1 + discount_rate) ** projection_years)
        equity = pv_proj + pv_tv - net_debt
        out[name] = {
            "valuation": round(equity / shares, 4),
            "terminal_growth_rate": g,
            "terminal_value": round(tv, 2),
            "pv_terminal_value": round(pv_tv, 2),
            "enterprise_value": round(pv_proj + pv_tv, 2),
            "equity_value": round(equity, 2),
        }
    return out


def rating_from_upside(upside: Optional[float]) -> str:
    if upside is None:
        return "HOLD"
    if upside >= 30:
        return "STRONG_BUY"
    if upside >= 15:
        return "BUY"
    if upside >= -15:
        return "HOLD"
    if upside >= -30:
        return "REDUCE"
    return "SELL"
