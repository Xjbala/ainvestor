# -*- coding: utf-8 -*-
"""
配额计量与订阅闸门。

核心流程：
  1. 判断身份（user_id 或 anonymous_key）
  2. 定位当前订阅窗口
     - 登录用户：读 active subscription + 对应窗口的 quota_grant
     - 匿名用户：用 free plan 兜底额度 + 滚动 30 天窗口
  3. 已用 = SUM(usage_events WHERE created_at IN [window_start, window_end])
  4. 超额 → 抛 HTTPException(402)（匿名）/ 429（登录）
  5. 写一条 usage_event（同一事务内）

匿名窗口规则（滚动 30 天）：
  window_start = max(最早一条 usage_event.created_at, now - 30d)
  window_end   = now
即首次使用时刻起算的 30 天，之后每次新使用都会顺延窗口起点，
但永远覆盖最近 30 天。简化实现：直接用 (now - 30d, now) 作为窗口。
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..persistence.orm_models import QuotaResource, SubscriptionStatus
from ..persistence.repository import (
    PlanRepository,
    QuotaGrantRepository,
    SubscriptionRepository,
    UsageEventRepository,
)

logger = logging.getLogger(__name__)

# ============================================================
# 配置
# ============================================================

ANON_COOKIE_NAME = os.getenv("ANON_COOKIE_NAME", "anon_id")
ANON_AI_ANALYSIS_QUOTA = int(os.getenv("ANON_AI_ANALYSIS_QUOTA", "1"))
ANON_EXPERT_QUOTA = int(os.getenv("ANON_EXPERT_QUOTA", "5"))
FREE_PLAN_CODE = os.getenv("FREE_PLAN_CODE", "free")
ANON_WINDOW_DAYS = int(os.getenv("ANON_WINDOW_DAYS", "30"))

# 资源 → 计划字段名映射
_RESOURCE_TO_PLAN_FIELD = {
    QuotaResource.AI_ANALYSIS: "ai_quota_monthly",
    QuotaResource.EXPERT_VALUATION: "expert_quota_monthly",
    QuotaResource.DATA_API: "data_api_quota_monthly",
}

# 资源 → grant 字段名映射
_RESOURCE_TO_GRANT_FIELD = {
    QuotaResource.AI_ANALYSIS: "ai_quota",
    QuotaResource.EXPERT_VALUATION: "expert_quota",
    QuotaResource.DATA_API: "data_api_quota",
}

# 资源 → 匿名额度环境变量映射
_RESOURCE_TO_ANON_QUOTA = {
    QuotaResource.AI_ANALYSIS: ANON_AI_ANALYSIS_QUOTA,
    QuotaResource.EXPERT_VALUATION: ANON_EXPERT_QUOTA,
    QuotaResource.DATA_API: 0,
}


# ============================================================
# 身份与窗口
# ============================================================

@dataclass
class Identity:
    """调用者身份。

    登录用户：user_id 非空。
    匿名用户：anonymous_key 非空（cookie UUID 的哈希）。
    """
    user_id: Optional[str]
    anonymous_key: Optional[str]
    ip_hash: Optional[str]

    @property
    def is_anonymous(self) -> bool:
        return self.user_id is None


@dataclass
class QuotaWindow:
    """配额计算窗口与额度上限。"""
    window_start: datetime
    window_end: datetime
    quota_limit: int
    plan_code: str


def hash_anonymous_key(raw_uuid: str) -> str:
    """对匿名 cookie UUID 做哈希后存储，避免明文落库可关联。

    同时支持把已哈希的值再传入时幂等（不再二次哈希）。
    """
    if not raw_uuid:
        return ""
    if len(raw_uuid) == 64 and all(c in "0123456789abcdef" for c in raw_uuid):
        return raw_uuid
    return hashlib.sha256(raw_uuid.encode("utf-8")).hexdigest()


def hash_ip(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:32]


def generate_anonymous_key() -> str:
    """生成新的匿名 cookie 值（UUID4）。"""
    import uuid
    return str(uuid.uuid4())


async def resolve_quota_window(
    session: AsyncSession,
    identity: Identity,
    resource: QuotaResource,
    now: Optional[datetime] = None,
) -> QuotaWindow:
    """解析当前身份在指定资源上的配额窗口与上限。

    登录用户：
      - 有 active 订阅 → 订阅窗口 + 对应 grant 的额度
      - 无订阅 → free plan 月度额度，按自然月窗口
    匿名用户：
      - 滚动 30 天窗口 + 环境变量额度
    """
    if now is None:
        now = datetime.utcnow()

    if identity.is_anonymous:
        window_start = now - timedelta(days=ANON_WINDOW_DAYS)
        return QuotaWindow(
            window_start=window_start,
            window_end=now,
            quota_limit=_RESOURCE_TO_ANON_QUOTA.get(resource, 0),
            plan_code=FREE_PLAN_CODE,
        )

    sub_repo = SubscriptionRepository(session)
    grant_repo = QuotaGrantRepository(session)
    plan_repo = PlanRepository(session)

    sub = await sub_repo.get_active_by_user(identity.user_id)
    if sub is not None:
        grant = await grant_repo.get_active_grant(identity.user_id, now=now)
        if grant is not None:
            quota_value = getattr(grant, _RESOURCE_TO_GRANT_FIELD[resource])
            return QuotaWindow(
                window_start=grant.period_start,
                window_end=grant.period_end,
                quota_limit=quota_value,
                plan_code=grant.plan_code,
            )
        # 有订阅但 grant 缺失（异常路径），回退到订阅窗口 + plan 额度
        plan = await plan_repo.get_by_code(sub.plan_code)
        if plan is not None:
            return QuotaWindow(
                window_start=sub.current_period_start,
                window_end=sub.current_period_end,
                quota_limit=getattr(plan, _RESOURCE_TO_PLAN_FIELD[resource]),
                plan_code=plan.code,
            )

    # 登录但无订阅 → free plan 月度额度
    plan = await plan_repo.get_by_code(FREE_PLAN_CODE)
    if plan is None:
        # plans 未 bootstrap 的兜底：给一个保守默认值
        fallback = {QuotaResource.AI_ANALYSIS: 3, QuotaResource.EXPERT_VALUATION: 10, QuotaResource.DATA_API: 0}
        return QuotaWindow(
            window_start=_month_start(now),
            window_end=_month_end(now),
            quota_limit=fallback.get(resource, 0),
            plan_code=FREE_PLAN_CODE,
        )
    return QuotaWindow(
        window_start=_month_start(now),
        window_end=_month_end(now),
        quota_limit=getattr(plan, _RESOURCE_TO_PLAN_FIELD[resource]),
        plan_code=plan.code,
    )


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _month_end(now: datetime) -> datetime:
    if now.month == 12:
        return now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


# ============================================================
# 主流程
# ============================================================

async def check_and_consume(
    session: AsyncSession,
    identity: Identity,
    resource: QuotaResource,
    amount: int = 1,
    analysis_session_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Tuple[int, int, QuotaWindow]:
    """检查配额并写入一条 usage_event。

    返回 (used, quota, window)：
      - used: 本次消耗后的已用量
      - quota: 当前窗口上限
      - window: 当前窗口信息

    超额时抛 HTTPException：
      - 匿名用户 → 402 Payment Required（引导注册/订阅）
      - 登录用户 → 429 Too Many Requests（引导升级订阅）
    """
    if now is None:
        now = datetime.utcnow()

    window = await resolve_quota_window(session, identity, resource, now=now)

    usage_repo = UsageEventRepository(session)
    used = await usage_repo.sum_in_window(
        resource=resource,
        window_start=window.window_start,
        window_end=window.window_end,
        user_id=identity.user_id,
        anonymous_key=identity.anonymous_key,
    )

    if used + amount > window.quota_limit:
        if identity.is_anonymous:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "quota_exceeded",
                    "message": "免费配额已用尽，注册或订阅以继续使用",
                    "resource": resource.value,
                    "used": used,
                    "quota": window.quota_limit,
                    "window_start": window.window_start.isoformat(),
                    "window_end": window.window_end.isoformat(),
                    "upgrade_url": "/register",
                },
            )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "quota_exceeded",
                "message": "当前订阅配额已用尽，请升级订阅",
                "resource": resource.value,
                "used": used,
                "quota": window.quota_limit,
                "window_start": window.window_start.isoformat(),
                "window_end": window.window_end.isoformat(),
            },
        )

    await usage_repo.create(
        resource=resource,
        amount=amount,
        user_id=identity.user_id,
        anonymous_key=identity.anonymous_key,
        ip_hash=identity.ip_hash,
        session_id=analysis_session_id,
    )

    logger.info(
        "quota consumed: ident=%s resource=%s amount=%s used=%s/%s plan=%s",
        identity.user_id or f"anon:{identity.anonymous_key}",
        resource.value, amount, used + amount, window.quota_limit, window.plan_code,
    )

    return used + amount, window.quota_limit, window


async def get_entitlements(
    session: AsyncSession,
    identity: Identity,
    now: Optional[datetime] = None,
) -> dict:
    """返回当前身份所有资源的额度与剩余。

    前端在调 AI 分析/专家估值前调一次，做配额展示。
    """
    if now is None:
        now = datetime.utcnow()

    usage_repo = UsageEventRepository(session)
    entitlements = {}
    for resource in (QuotaResource.AI_ANALYSIS, QuotaResource.EXPERT_VALUATION, QuotaResource.DATA_API):
        window = await resolve_quota_window(session, identity, resource, now=now)
        used = await usage_repo.sum_in_window(
            resource=resource,
            window_start=window.window_start,
            window_end=window.window_end,
            user_id=identity.user_id,
            anonymous_key=identity.anonymous_key,
        )
        entitlements[resource.value] = {
            "used": used,
            "quota": window.quota_limit,
            "remaining": max(0, window.quota_limit - used),
            "window_start": window.window_start.isoformat(),
            "window_end": window.window_end.isoformat(),
        }

    # 当前订阅状态（仅登录用户）
    subscription_info = None
    if identity.user_id:
        sub_repo = SubscriptionRepository(session)
        sub = await sub_repo.get_active_by_user(identity.user_id)
        if sub:
            subscription_info = {
                "plan_code": sub.plan_code,
                "status": sub.status.value,
                "current_period_start": sub.current_period_start.isoformat(),
                "current_period_end": sub.current_period_end.isoformat(),
                "cancel_at_period_end": sub.cancel_at_period_end,
            }

    return {
        "is_anonymous": identity.is_anonymous,
        "plan_code": (await resolve_quota_window(session, identity, QuotaResource.AI_ANALYSIS, now=now)).plan_code,
        "subscription": subscription_info,
        "entitlements": entitlements,
    }


async def migrate_anonymous_usage(
    session: AsyncSession,
    anonymous_key: str,
    user_id: str,
) -> int:
    """注册成功时把匿名 key 名下的用量迁移到新 user_id。"""
    usage_repo = UsageEventRepository(session)
    count = await usage_repo.migrate_anonymous_to_user(anonymous_key, user_id)
    if count:
        logger.info("migrated %s anonymous usage events to user=%s", count, user_id)
    return count
