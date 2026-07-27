# -*- coding: utf-8 -*-
"""
行业估值画像：方法适用性、默认 beta、WACC 区间、退出倍数等。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# 行业关键词 → 画像（名称模糊匹配）
_INDUSTRY_KEYWORDS: List[tuple[tuple[str, ...], str]] = [
    (("银行", "bank"), "bank"),
    (("保险", "insurance"), "insurance"),
    (("证券", "broker", "券商"), "financial"),
    (("公用", "电力", "水务", "燃气", "utility"), "utility"),
    (("电信", "通信", "运营商", "telecom"), "telecom"),
    (("白酒", "食品", "饮料", "消费", "家电", "staples"), "consumer_staples"),
    (("医药", "生物", "医疗", "pharma", "biotech"), "healthcare"),
    (("软件", "互联网", "信息", "计算机", "saas", "云计算"), "tech"),
    (("半导体", "芯片", "电子"), "semiconductor"),
    (("汽车", "新能源车"), "auto"),
    (("石油", "煤炭", "有色", "钢铁", "能源"), "energy"),
    (("地产", "房地产", "reits"), "real_estate"),
    (("机械", "制造", "工业", "军工"), "industrial"),
    (("零售", "商贸", "电商"), "retail"),
]

PROFILES: Dict[str, Dict[str, Any]] = {
    "default": {
        "beta": 1.0,
        "wacc_band": (0.08, 0.12),
        "exit_ev_ebitda": 12.0,
        "terminal_g_cap": 0.03,
        "methods": {"DCF": "primary", "RI": "secondary", "RELATIVE": "yes", "SOTP": "optional"},
        "relative_primary": "pe",
        "size_premium": 0.0,
    },
    "bank": {
        "beta": 1.05,
        "wacc_band": (0.09, 0.12),
        "exit_ev_ebitda": 8.0,
        "terminal_g_cap": 0.025,
        "methods": {"DCF": "skip", "RI": "secondary", "RELATIVE": "primary", "SOTP": "optional"},
        "relative_primary": "pb",
        "size_premium": 0.0,
    },
    "insurance": {
        "beta": 1.1,
        "wacc_band": (0.09, 0.12),
        "exit_ev_ebitda": 9.0,
        "terminal_g_cap": 0.025,
        "methods": {"DCF": "skip", "RI": "secondary", "RELATIVE": "primary", "SOTP": "optional"},
        "relative_primary": "pb",
        "size_premium": 0.0,
    },
    "financial": {
        "beta": 1.15,
        "wacc_band": (0.09, 0.13),
        "exit_ev_ebitda": 10.0,
        "terminal_g_cap": 0.025,
        "methods": {"DCF": "low", "RI": "secondary", "RELATIVE": "primary", "SOTP": "optional"},
        "relative_primary": "pb",
        "size_premium": 0.0,
    },
    "utility": {
        "beta": 0.6,
        "wacc_band": (0.06, 0.09),
        "exit_ev_ebitda": 10.0,
        "terminal_g_cap": 0.025,
        "methods": {"DCF": "primary", "RI": "secondary", "RELATIVE": "yes", "SOTP": "no"},
        "relative_primary": "pe",
        "size_premium": 0.0,
    },
    "telecom": {
        "beta": 0.85,
        "wacc_band": (0.07, 0.10),
        "exit_ev_ebitda": 8.0,
        "terminal_g_cap": 0.025,
        "methods": {"DCF": "primary", "RI": "secondary", "RELATIVE": "yes", "SOTP": "optional"},
        "relative_primary": "ev_ebitda",
        "size_premium": 0.0,
    },
    "consumer_staples": {
        "beta": 0.75,
        "wacc_band": (0.07, 0.10),
        "exit_ev_ebitda": 14.0,
        "terminal_g_cap": 0.03,
        "methods": {"DCF": "primary", "RI": "secondary", "RELATIVE": "yes", "SOTP": "optional"},
        "relative_primary": "pe",
        "size_premium": 0.0,
    },
    "healthcare": {
        "beta": 0.95,
        "wacc_band": (0.08, 0.11),
        "exit_ev_ebitda": 15.0,
        "terminal_g_cap": 0.03,
        "methods": {"DCF": "primary", "RI": "secondary", "RELATIVE": "yes", "SOTP": "optional"},
        "relative_primary": "pe",
        "size_premium": 0.0,
    },
    "tech": {
        "beta": 1.2,
        "wacc_band": (0.09, 0.13),
        "exit_ev_ebitda": 18.0,
        "terminal_g_cap": 0.035,
        "methods": {"DCF": "secondary", "RI": "yes", "RELATIVE": "primary", "SOTP": "optional"},
        "relative_primary": "ev_sales",
        "size_premium": 0.005,
    },
    "semiconductor": {
        "beta": 1.35,
        "wacc_band": (0.10, 0.13),
        "exit_ev_ebitda": 16.0,
        "terminal_g_cap": 0.03,
        "methods": {"DCF": "yes", "RI": "yes", "RELATIVE": "primary", "SOTP": "no"},
        "relative_primary": "ev_ebitda",
        "size_premium": 0.01,
    },
    "auto": {
        "beta": 1.25,
        "wacc_band": (0.09, 0.12),
        "exit_ev_ebitda": 10.0,
        "terminal_g_cap": 0.025,
        "methods": {"DCF": "yes", "RI": "yes", "RELATIVE": "yes", "SOTP": "optional"},
        "relative_primary": "pe",
        "size_premium": 0.005,
    },
    "energy": {
        "beta": 1.15,
        "wacc_band": (0.09, 0.12),
        "exit_ev_ebitda": 8.0,
        "terminal_g_cap": 0.02,
        "methods": {"DCF": "yes", "RI": "secondary", "RELATIVE": "yes", "SOTP": "optional"},
        "relative_primary": "ev_ebitda",
        "size_premium": 0.0,
    },
    "real_estate": {
        "beta": 1.1,
        "wacc_band": (0.08, 0.12),
        "exit_ev_ebitda": 8.0,
        "terminal_g_cap": 0.02,
        "methods": {"DCF": "low", "RI": "yes", "RELATIVE": "primary", "SOTP": "optional"},
        "relative_primary": "pb",
        "size_premium": 0.005,
    },
    "industrial": {
        "beta": 1.05,
        "wacc_band": (0.08, 0.11),
        "exit_ev_ebitda": 11.0,
        "terminal_g_cap": 0.03,
        "methods": {"DCF": "primary", "RI": "secondary", "RELATIVE": "yes", "SOTP": "optional"},
        "relative_primary": "ev_ebitda",
        "size_premium": 0.0,
    },
    "retail": {
        "beta": 1.1,
        "wacc_band": (0.08, 0.12),
        "exit_ev_ebitda": 12.0,
        "terminal_g_cap": 0.025,
        "methods": {"DCF": "yes", "RI": "yes", "RELATIVE": "yes", "SOTP": "optional"},
        "relative_primary": "pe",
        "size_premium": 0.0,
    },
}


def resolve_profile_key(industry_name: Optional[str]) -> str:
    if not industry_name:
        return "default"
    name = industry_name.lower()
    for keywords, key in _INDUSTRY_KEYWORDS:
        for kw in keywords:
            if kw.lower() in name or kw in industry_name:
                return key
    return "default"


def get_industry_profile(industry_name: Optional[str] = None) -> Dict[str, Any]:
    key = resolve_profile_key(industry_name)
    profile = dict(PROFILES.get(key, PROFILES["default"]))
    profile["profile_key"] = key
    profile["industry_name"] = industry_name
    return profile


def method_weight(
    industry_name: Optional[str],
    *,
    has_dcf: bool,
    has_ri: bool,
    has_relative: bool,
    has_sotp: bool = False,
) -> Dict[str, float]:
    """按行业与可用方法生成归一化权重。"""
    profile = get_industry_profile(industry_name)
    methods = profile.get("methods", {})

    raw: Dict[str, float] = {"DCF": 0.0, "RI": 0.0, "RELATIVE": 0.0, "SOTP": 0.0}
    score_map = {"primary": 1.0, "yes": 0.7, "secondary": 0.5, "low": 0.25, "optional": 0.3, "skip": 0.0, "no": 0.0}

    if has_dcf:
        raw["DCF"] = score_map.get(str(methods.get("DCF", "yes")), 0.5)
    if has_ri:
        raw["RI"] = score_map.get(str(methods.get("RI", "yes")), 0.5)
    if has_relative:
        raw["RELATIVE"] = score_map.get(str(methods.get("RELATIVE", "yes")), 0.5)
    if has_sotp:
        raw["SOTP"] = score_map.get(str(methods.get("SOTP", "optional")), 0.3)

    # 金融业：抑制 DCF
    if profile.get("profile_key") in ("bank", "insurance", "financial"):
        raw["DCF"] = 0.0 if not has_dcf else min(raw["DCF"], 0.1)

    total = sum(raw.values())
    if total <= 0:
        # 均分可用方法
        n = sum(1 for k, v in (("DCF", has_dcf), ("RI", has_ri), ("RELATIVE", has_relative), ("SOTP", has_sotp)) if v)
        if n == 0:
            return raw
        eq = 1.0 / n
        return {
            "DCF": eq if has_dcf else 0.0,
            "RI": eq if has_ri else 0.0,
            "RELATIVE": eq if has_relative else 0.0,
            "SOTP": eq if has_sotp else 0.0,
        }

    return {k: round(v / total, 4) for k, v in raw.items()}
