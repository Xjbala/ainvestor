# -*- coding: utf-8 -*-
"""
管理员订阅管理 API。

目前不接支付网关，admin 手动开通/续期/取消订阅。
开通时同步创建一行 quota_grant（额度取自 plan 的月度配额，周期默认 1 个月）。
续期 = 把 current_period_end 推后 + 新建一行 grant（append-only）。
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import require_admin
from ..persistence.db import get_db_session
from ..persistence.orm_models import SubscriptionStatus, User, UserRole
from ..persistence.repository import (
    PlanRepository,
    QuotaGrantRepository,
    SubscriptionRepository,
    UserRepository,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["管理员-订阅管理"])


# ============================================================
# 请求/响应模型
# ============================================================

class CreateSubscriptionRequest(BaseModel):
    """开通订阅请求"""
    user_id: str = Field(..., description="被开通用户ID")
    plan_code: str = Field(..., description="计划代码 (free/pro/enterprise)")
    period_days: int = Field(30, ge=1, le=365, description="订阅周期天数，默认 30")
    note: Optional[str] = Field(None, max_length=500, description="管理员备注")


class ExtendSubscriptionRequest(BaseModel):
    """续期订阅请求"""
    period_days: int = Field(30, ge=1, le=365, description="续期天数")
    plan_code: Optional[str] = Field(None, description="续期时切换计划，不传则保持原计划")
    note: Optional[str] = Field(None, max_length=500)


class UpdateSubscriptionStatusRequest(BaseModel):
    """更新订阅状态请求"""
    status: str = Field(..., description="新状态: active/canceled/expired/past_due")
    cancel_at_period_end: Optional[bool] = None


class SubscriptionResponse(BaseModel):
    id: str
    user_id: str
    plan_code: str
    status: str
    current_period_start: str
    current_period_end: str
    cancel_at_period_end: bool
    activated_by_admin_id: Optional[str] = None
    note: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SubscriptionListResponse(BaseModel):
    subscriptions: List[SubscriptionResponse]
    total: int
    skip: int
    limit: int


class PlanResponse(BaseModel):
    code: str
    name: str
    ai_quota_monthly: int
    expert_quota_monthly: int
    data_api_quota_monthly: int
    price_cents: int
    is_active: bool
    sort_order: int

    class Config:
        from_attributes = True


class PlanListResponse(BaseModel):
    plans: List[PlanResponse]


class MessageResponse(BaseModel):
    message: str


# ============================================================
# 计划查询
# ============================================================

@router.get("/plans", response_model=PlanListResponse)
async def list_plans(
    only_active: bool = Query(False, description="仅返回在售计划"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> PlanListResponse:
    """列出所有订阅计划。"""
    plan_repo = PlanRepository(session)
    plans = await plan_repo.list_all(only_active=only_active)
    return PlanListResponse(
        plans=[PlanResponse.model_validate(p) for p in plans],
    )


# ============================================================
# 订阅管理
# ============================================================

def _to_response(sub) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=sub.id,
        user_id=sub.user_id,
        plan_code=sub.plan_code,
        status=sub.status.value,
        current_period_start=sub.current_period_start.isoformat(),
        current_period_end=sub.current_period_end.isoformat(),
        cancel_at_period_end=sub.cancel_at_period_end,
        activated_by_admin_id=sub.activated_by_admin_id,
        note=sub.note,
        created_at=sub.created_at.isoformat(),
        updated_at=sub.updated_at.isoformat(),
    )


@router.get("/subscriptions", response_model=SubscriptionListResponse)
async def list_subscriptions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = Query(None, description="按用户过滤"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> SubscriptionListResponse:
    """列出订阅记录（最近优先）。"""
    sub_repo = SubscriptionRepository(session)
    subs = await sub_repo.list_all(skip=skip, limit=limit, user_id=user_id)
    return SubscriptionListResponse(
        subscriptions=[_to_response(s) for s in subs],
        total=len(subs),
        skip=skip,
        limit=limit,
    )


@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    request: CreateSubscriptionRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> SubscriptionResponse:
    """开通订阅（admin 手动）。

    同一用户已有 active 订阅时拒绝，应改用续期接口。
    开通时同步创建 quota_grant。
    """
    user_repo = UserRepository(session)
    target_user = await user_repo.get_by_id(request.user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    plan_repo = PlanRepository(session)
    plan = await plan_repo.get_by_code(request.plan_code)
    if plan is None or not plan.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="计划不存在或已下架")

    sub_repo = SubscriptionRepository(session)
    existing = await sub_repo.get_active_by_user(request.user_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该用户已有生效中的订阅，请改用续期接口",
        )

    now = datetime.utcnow()
    period_start = now
    period_end = now + timedelta(days=request.period_days)

    sub = await sub_repo.create(
        user_id=request.user_id,
        plan_code=request.plan_code,
        current_period_start=period_start,
        current_period_end=period_end,
        activated_by_admin_id=current_user.id,
        note=request.note,
    )

    grant_repo = QuotaGrantRepository(session)
    await grant_repo.create(
        user_id=request.user_id,
        plan_code=request.plan_code,
        period_start=period_start,
        period_end=period_end,
        ai_quota=plan.ai_quota_monthly,
        expert_quota=plan.expert_quota_monthly,
        data_api_quota=plan.data_api_quota_monthly,
        source_subscription_id=sub.id,
    )

    logger.info(
        "subscription created: user=%s plan=%s period_days=%s by_admin=%s",
        request.user_id, request.plan_code, request.period_days, current_user.id,
    )
    return _to_response(sub)


@router.post("/subscriptions/{sub_id}/extend", response_model=SubscriptionResponse)
async def extend_subscription(
    sub_id: str,
    request: ExtendSubscriptionRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> SubscriptionResponse:
    """续期订阅。

    把 current_period_end 推后 period_days 天，并新建一行 quota_grant。
    可在续期时切换 plan（plan_code 非空时）。
    """
    sub_repo = SubscriptionRepository(session)
    sub = await sub_repo.get_by_id(sub_id)
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订阅不存在")

    new_plan_code = request.plan_code or sub.plan_code
    plan_repo = PlanRepository(session)
    plan = await plan_repo.get_by_code(new_plan_code)
    if plan is None or not plan.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="计划不存在或已下架")

    now = datetime.utcnow()
    base = max(sub.current_period_end, now)
    new_start = base
    new_end = base + timedelta(days=request.period_days)

    await sub_repo.extend_period(sub_id, new_start, new_end)
    if new_plan_code != sub.plan_code:
        sub.plan_code = new_plan_code
        await session.flush()

    grant_repo = QuotaGrantRepository(session)
    await grant_repo.create(
        user_id=sub.user_id,
        plan_code=new_plan_code,
        period_start=new_start,
        period_end=new_end,
        ai_quota=plan.ai_quota_monthly,
        expert_quota=plan.expert_quota_monthly,
        data_api_quota=plan.data_api_quota_monthly,
        source_subscription_id=sub.id,
    )

    await session.refresh(sub)
    logger.info(
        "subscription extended: sub=%s new_end=%s by_admin=%s",
        sub_id, new_end.isoformat(), current_user.id,
    )
    return _to_response(sub)


@router.patch("/subscriptions/{sub_id}/status", response_model=SubscriptionResponse)
async def update_subscription_status(
    sub_id: str,
    request: UpdateSubscriptionStatusRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> SubscriptionResponse:
    """更新订阅状态（如手动取消/重新激活）。"""
    try:
        new_status = SubscriptionStatus(request.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的状态: {request.status}",
        )

    sub_repo = SubscriptionRepository(session)
    sub = await sub_repo.get_by_id(sub_id)
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订阅不存在")

    sub.status = new_status
    if request.cancel_at_period_end is not None:
        sub.cancel_at_period_end = request.cancel_at_period_end
    await session.flush()
    await session.refresh(sub)

    logger.info(
        "subscription status updated: sub=%s new_status=%s by_admin=%s",
        sub_id, new_status.value, current_user.id,
    )
    return _to_response(sub)
