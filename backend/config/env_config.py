# -*- coding: utf-8 -*-
# @Time: 2026/1/27 15:43
# @Author : aceplus
# @Desc : ==============================================
# Life is Short I Use Python!!!                      ===
# If this runs wrong,don't ask me,I don't know why.  ===
# If this runs right,thank god,and I don't know why. ===
# Maybe the answer,my friend,is blowing in the wind. ===
# ======================================================
# @Project : ZHANGXJ
# @FileName: env_config.py
# @Software: PyCharm
import os


def get_env_list(key: str, default: list = None) -> list:
    """Get comma-separated list from env"""
    value = os.getenv(key, "")
    if not value:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


def get_env_float(key: str, default: float = 0.0) -> float:
    """Get float from env"""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def get_env_int(key: str, default: int = 0) -> int:
    """Get int from env"""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default
