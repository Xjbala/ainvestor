# -*- coding: utf-8 -*-
"""
Cloudflare Turnstile 人机验证

前端渲染 widget 拿到 token，后端调 siteverify 校验。
未配置 TURNSTILE_SECRET_KEY 时跳过校验（开发环境）。
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_TURNSTILE_SECRET = os.getenv("TURNSTILE_SECRET_KEY", "")
_TURNSTILE_SECRET_DEFAULT = "1x0000000000000000000000000000000AA"  # Cloudflare 测试用 secret（永远通过）


def get_turnstile_site_key() -> str:
    """前端用的 site key（公开值）"""
    return os.getenv("TURNSTILE_SITE_KEY", "")


def is_turnstile_enabled() -> bool:
    return bool(_TURNSTILE_SECRET)


async def verify_turnstile_token(token: str, remote_ip: str | None = None) -> bool:
    """
    校验 Turnstile token。

    未配置 secret 时跳过（开发环境），生产必须配置。
    """
    if not _TURNSTILE_SECRET:
        logger.warning("Turnstile 未配置 TURNSTILE_SECRET_KEY，跳过校验（仅开发环境允许）")
        return True

    if not token:
        return False

    data = {
        "secret": _TURNSTILE_SECRET,
        "response": token,
    }
    if remote_ip:
        data["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(TURNSTILE_VERIFY_URL, data=data)
            resp.raise_for_status()
            result = resp.json()
    except Exception:
        logger.exception("Turnstile 校验请求失败")
        return False

    if not result.get("success", False):
        logger.warning("Turnstile 校验失败: %s", result.get("error-codes"))
        return False

    return True
