# -*- coding: utf-8 -*-
"""加载以平安银行 000001 新浪报表审核的银行标准科目目录。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


CATALOG_PATH = Path(__file__).parent / "data" / "bank_subjects_000001.json"


def load_bank_subject_catalog() -> Dict[str, Any]:
    """返回标准科目、来源别名和待拒绝来源项。"""
    with CATALOG_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    for key in ("subjects", "aliases", "rejected"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"银行科目目录格式错误: {key} 必须为列表")
    return data
