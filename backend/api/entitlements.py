# -*- coding: utf-8 -*-
"""
当前用户/匿名的订阅与配额查询。

匿名用户同样可访问，返回 free plan 兜底额度 + 滚动 30 天窗口内的剩余。
前端在调 AI 分析/专家估值前调一次，做配额展示与额度耗尽引导。
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_anonymous_or_user
from ..core.quota import Identity, get_entitlements
from ..persistence.db import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/me", tags=["我的账户"])


@router.get("/entitlements", response_model=Dict[str, Any])
async def get_my_entitlements(
    identity_user=Depends(get_anonymous_or_user),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """返回当前身份的订阅状态与各资源剩余配额。"""
    identity: Identity = identity_user[0]
    return await get_entitlements(session, identity)
