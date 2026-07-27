# -*- coding: utf-8 -*-
"""
交易所 API 路由

提供交易所信息的查询接口。
"""

import logging
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..persistence.db import get_db_session
from ..persistence.financial_models import Exchange

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/exchanges", tags=["交易所管理"])


# ============================================================
# 请求/响应模型
# ============================================================

class ExchangeResponse(BaseModel):
    id: int
    code: str
    name: str
    country: str
    is_active: bool

    class Config:
        from_attributes = True


# ============================================================
# 路由实现
# ============================================================

@router.get("", response_model=List[ExchangeResponse])
async def list_exchanges(session: AsyncSession = Depends(get_db_session)):
    """
    获取所有激活的交易所列表
    """
    stmt = select(Exchange).where(Exchange.is_active == True)
    result = await session.execute(stmt)
    exchanges = result.scalars().all()
    
    return [
        ExchangeResponse(
            id=e.id,
            code=e.code,
            name=e.name,
            country=e.country,
            is_active=e.is_active
        )
        for e in exchanges
    ]
