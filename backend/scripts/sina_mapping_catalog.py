# -*- coding: utf-8 -*-
"""加载经过人工审核的新浪科目映射目录。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .bank_subject_catalog import load_bank_subject_catalog


CATALOG_PATH = Path(__file__).parent / "data" / "sina_subject_mappings.json"


def load_sina_subject_mapping_catalog() -> Dict[str, Any]:
    """返回新浪字段的主名称、别名和拒绝项目录。"""
    with CATALOG_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    for key in ("primary_sina_names", "aliases", "rejected"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"新浪映射目录格式错误: {key} 必须为列表")
    return data


def rejected_sina_subject_mappings() -> Dict[str, Dict[str, str]]:
    """返回不可自动映射的新浪字段及其审核理由。"""
    rejected: Dict[str, Dict[str, str]] = {}
    catalogs = (
        load_sina_subject_mapping_catalog()["rejected"],
        load_bank_subject_catalog()["rejected"],
    )
    for catalog in catalogs:
        for item in catalog:
            report_type = str(item["report_type"]).upper()
            source_name = str(item["source_name"]).strip()
            reason = str(item["reason"]).strip()
            if source_name in rejected.setdefault(report_type, {}):
                raise ValueError(f"新浪拒绝目录存在重复字段: {report_type} {source_name}")
            rejected[report_type][source_name] = reason
    return rejected
