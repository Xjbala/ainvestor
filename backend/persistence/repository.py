# -*- coding: utf-8 -*-
"""
数据仓库（Repository）模式

提供对数据库操作的高级封装，隔离业务逻辑和数据访问层。
保持与原 database.py 接口的兼容性，同时支持新的 ORM 模型。
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .orm_models import (
    AgentOutput,
    AgentPhase,
    AnalysisSession,
    Plan,
    QuotaGrant,
    QuotaResource,
    RatingReport,
    SessionStatus,
    Subscription,
    SubscriptionStatus,
    UsageEvent,
    User,
    UserRole,
)

logger = logging.getLogger(__name__)


# ============================================================
# 会话仓库
# ============================================================

class SessionRepository:
    """
    分析会话数据访问类

    提供 CRUD 操作，兼容原有接口。
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        tickers: List[str],
        date: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> AnalysisSession:
        """
        创建分析会话

        Args:
            tickers: 股票代码列表
            date: 分析日期
            session_id: 可选的会话ID（如不提供则自动生成）
            user_id: 可选的用户ID

        Returns:
            创建的会话对象
        """
        analysis_session = AnalysisSession(
            tickers=json.dumps(tickers),
            date=date,
            user_id=user_id,
            status=SessionStatus.PENDING,
        )
        if session_id:
            analysis_session.id = session_id

        self.session.add(analysis_session)
        await self.session.flush()
        await self.session.refresh(analysis_session)

        logger.info(f"Created session: {analysis_session.id}")
        return analysis_session

    async def get_by_id(self, session_id: str) -> Optional[AnalysisSession]:
        """根据 ID 获取会话"""
        result = await self.session.execute(
            select(AnalysisSession).where(AnalysisSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_recent(
        self,
        limit: int = 10,
        user_id: Optional[str] = None,
    ) -> List[AnalysisSession]:
        """
        获取最近的会话列表

        Args:
            limit: 返回数量限制
            user_id: 可选的用户ID过滤

        Returns:
            会话列表，按创建时间倒序
        """
        query = select(AnalysisSession).order_by(
            AnalysisSession.created_at.desc()
        ).limit(limit)

        if user_id:
            query = query.where(AnalysisSession.user_id == user_id)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self,
        session_id: str,
        status: SessionStatus,
    ) -> bool:
        """
        更新会话状态

        Args:
            session_id: 会话ID
            status: 新状态

        Returns:
            是否更新成功
        """
        analysis_session = await self.get_by_id(session_id)
        if not analysis_session:
            return False

        analysis_session.status = status

        # 如果是终态，设置完成时间
        if status in (SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.CANCELLED):
            analysis_session.completed_at = datetime.now()

        await self.session.flush()
        logger.info(f"Session {session_id} status updated to {status}")
        return True


# ============================================================
# Agent 输出仓库
# ============================================================

class AgentOutputRepository:
    """Agent 输出数据访问类"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(
        self,
        session_id: str,
        agent_id: str,
        agent_type: str,
        phase: str,
        content: str,
    ) -> AgentOutput:
        """
        保存 Agent 输出

        Args:
            session_id: 会话ID
            agent_id: Agent标识
            agent_type: Agent类型
            phase: 执行阶段
            content: 输出内容

        Returns:
            保存的输出对象
        """
        # 将字符串 phase 转换为枚举
        phase_enum = AgentPhase(phase) if isinstance(phase, str) else phase

        output = AgentOutput(
            session_id=session_id,
            agent_id=agent_id,
            agent_type=agent_type,
            phase=phase_enum,
            content=content,
        )

        self.session.add(output)
        await self.session.flush()
        await self.session.refresh(output)

        logger.debug(f"Saved agent output: {output.id}")
        return output

    async def get_by_session(self, session_id: str) -> List[AgentOutput]:
        """获取会话的所有 Agent 输出"""
        result = await self.session.execute(
            select(AgentOutput)
            .where(AgentOutput.session_id == session_id)
            .order_by(AgentOutput.created_at.asc())
        )
        return list(result.scalars().all())


# ============================================================
# 报告仓库
# ============================================================

class ReportRepository:
    """评级报告数据访问类"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(
        self,
        session_id: str,
        report_content: str,
        recommendations: Optional[dict] = None,
    ) -> RatingReport:
        """
        保存评级报告（如存在则更新）

        Args:
            session_id: 会话ID
            report_content: 报告内容
            recommendations: 投资建议

        Returns:
            保存的报告对象
        """
        # 检查是否已存在报告
        existing = await self.get_by_session(session_id)

        if existing:
            existing.report_content = report_content
            existing.recommendations = json.dumps(recommendations) if recommendations else None
            await self.session.flush()
            return existing

        report = RatingReport(
            session_id=session_id,
            report_content=report_content,
            recommendations=json.dumps(recommendations) if recommendations else None,
        )

        self.session.add(report)
        await self.session.flush()
        await self.session.refresh(report)

        logger.info(f"Saved report for session: {session_id}")
        return report

    async def get_by_session(self, session_id: str) -> Optional[RatingReport]:
        """获取会话的评级报告"""
        result = await self.session.execute(
            select(RatingReport).where(RatingReport.session_id == session_id)
        )
        return result.scalar_one_or_none()


# ============================================================
# 用户仓库
# ============================================================

class UserRepository:
    """用户数据访问类"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        username: str,
        email: str,
        hashed_password: str,
        role: UserRole = UserRole.USER,
        email_verified: bool = False,
    ) -> User:
        """
        创建用户

        Args:
            username: 用户名
            email: 邮箱
            hashed_password: 加密后的密码
            role: 用户角色
            email_verified: 邮箱是否已验证

        Returns:
            创建的用户对象
        """
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            role=role,
            email_verified=email_verified,
        )

        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)

        logger.info(f"Created user: {user.username}")
        return user

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """根据 ID 获取用户"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[User]:
        """获取用户列表（分页）"""
        result = await self.session.execute(
            select(User)
            .order_by(User.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_role(self, user_id: str, role: UserRole) -> bool:
        """更新用户角色"""
        user = await self.get_by_id(user_id)
        if not user:
            return False

        user.role = role
        await self.session.flush()
        return True

    async def deactivate(self, user_id: str) -> bool:
        """停用用户"""
        user = await self.get_by_id(user_id)
        if not user:
            return False

        user.is_active = False
        await self.session.flush()
        return True


# ============================================================
# 订阅与配额仓库
# ============================================================

class PlanRepository:
    """订阅计划目录数据访问类"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        code: str,
        name: str,
        ai_quota_monthly: int = 0,
        expert_quota_monthly: int = 0,
        data_api_quota_monthly: int = 0,
        price_cents: int = 0,
        is_active: bool = True,
        sort_order: int = 0,
    ) -> Plan:
        plan = Plan(
            code=code,
            name=name,
            ai_quota_monthly=ai_quota_monthly,
            expert_quota_monthly=expert_quota_monthly,
            data_api_quota_monthly=data_api_quota_monthly,
            price_cents=price_cents,
            is_active=is_active,
            sort_order=sort_order,
        )
        self.session.add(plan)
        await self.session.flush()
        return plan

    async def get_by_code(self, code: str) -> Optional[Plan]:
        result = await self.session.execute(
            select(Plan).where(Plan.code == code)
        )
        return result.scalar_one_or_none()

    async def list_all(self, only_active: bool = False) -> List[Plan]:
        query = select(Plan).order_by(Plan.sort_order.asc(), Plan.code.asc())
        if only_active:
            query = query.where(Plan.is_active.is_(True))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def upsert(
        self,
        code: str,
        name: str,
        ai_quota_monthly: int = 0,
        expert_quota_monthly: int = 0,
        data_api_quota_monthly: int = 0,
        price_cents: int = 0,
        is_active: bool = True,
        sort_order: int = 0,
    ) -> Plan:
        """幂等创建/更新计划。已存在则更新非空字段。"""
        existing = await self.get_by_code(code)
        if existing is None:
            return await self.create(
                code=code,
                name=name,
                ai_quota_monthly=ai_quota_monthly,
                expert_quota_monthly=expert_quota_monthly,
                data_api_quota_monthly=data_api_quota_monthly,
                price_cents=price_cents,
                is_active=is_active,
                sort_order=sort_order,
            )
        existing.name = name
        existing.ai_quota_monthly = ai_quota_monthly
        existing.expert_quota_monthly = expert_quota_monthly
        existing.data_api_quota_monthly = data_api_quota_monthly
        existing.price_cents = price_cents
        existing.is_active = is_active
        existing.sort_order = sort_order
        await self.session.flush()
        return existing


class SubscriptionRepository:
    """用户订阅状态数据访问类"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: str,
        plan_code: str,
        current_period_start: datetime,
        current_period_end: datetime,
        activated_by_admin_id: Optional[str] = None,
        note: Optional[str] = None,
        status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    ) -> Subscription:
        sub = Subscription(
            user_id=user_id,
            plan_code=plan_code,
            status=status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            activated_by_admin_id=activated_by_admin_id,
            note=note,
        )
        self.session.add(sub)
        await self.session.flush()
        return sub

    async def get_by_id(self, sub_id: str) -> Optional[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(Subscription.id == sub_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_user(self, user_id: str) -> Optional[Subscription]:
        """获取用户当前生效的订阅（status=active 且未过期）。"""
        now = datetime.utcnow()
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.current_period_end > now,
            )
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 50,
        user_id: Optional[str] = None,
    ) -> List[Subscription]:
        query = select(Subscription).order_by(
            Subscription.created_at.desc()
        ).offset(skip).limit(limit)
        if user_id:
            query = query.where(Subscription.user_id == user_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_user(self, user_id: str) -> List[Subscription]:
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        sub_id: str,
        status: SubscriptionStatus,
    ) -> bool:
        sub = await self.get_by_id(sub_id)
        if not sub:
            return False
        sub.status = status
        await self.session.flush()
        return True

    async def extend_period(
        self,
        sub_id: str,
        new_start: datetime,
        new_end: datetime,
    ) -> bool:
        """续期：推后 current_period_end。"""
        sub = await self.get_by_id(sub_id)
        if not sub:
            return False
        sub.current_period_start = new_start
        sub.current_period_end = new_end
        sub.status = SubscriptionStatus.ACTIVE
        await self.session.flush()
        return True


class QuotaGrantRepository:
    """配额发放记录数据访问类"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: str,
        plan_code: str,
        period_start: datetime,
        period_end: datetime,
        ai_quota: int = 0,
        expert_quota: int = 0,
        data_api_quota: int = 0,
        source_subscription_id: Optional[str] = None,
    ) -> QuotaGrant:
        grant = QuotaGrant(
            user_id=user_id,
            plan_code=plan_code,
            period_start=period_start,
            period_end=period_end,
            ai_quota=ai_quota,
            expert_quota=expert_quota,
            data_api_quota=data_api_quota,
            source_subscription_id=source_subscription_id,
        )
        self.session.add(grant)
        await self.session.flush()
        return grant

    async def get_active_grant(
        self,
        user_id: str,
        now: Optional[datetime] = None,
    ) -> Optional[QuotaGrant]:
        """获取用户当前窗口内的 grant（period_start <= now < period_end）。

        返回最近一条；正常情况下同一用户在任一时间点只应有一条有效 grant。
        """
        if now is None:
            now = datetime.utcnow()
        result = await self.session.execute(
            select(QuotaGrant)
            .where(
                QuotaGrant.user_id == user_id,
                QuotaGrant.period_start <= now,
                QuotaGrant.period_end > now,
            )
            .order_by(QuotaGrant.period_end.desc())
        )
        return result.scalars().first()

    async def list_by_user(
        self,
        user_id: str,
        limit: int = 20,
    ) -> List[QuotaGrant]:
        result = await self.session.execute(
            select(QuotaGrant)
            .where(QuotaGrant.user_id == user_id)
            .order_by(QuotaGrant.period_end.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class UsageEventRepository:
    """配额计量事件流数据访问类（append-only）"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        resource: QuotaResource,
        amount: int = 1,
        user_id: Optional[str] = None,
        anonymous_key: Optional[str] = None,
        ip_hash: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> UsageEvent:
        if user_id is None and anonymous_key is None:
            raise ValueError("usage event 需要 user_id 或 anonymous_key 至少一个")
        event = UsageEvent(
            user_id=user_id,
            anonymous_key=anonymous_key,
            ip_hash=ip_hash,
            resource=resource,
            amount=amount,
            session_id=session_id,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def sum_in_window(
        self,
        resource: QuotaResource,
        window_start: datetime,
        window_end: datetime,
        user_id: Optional[str] = None,
        anonymous_key: Optional[str] = None,
    ) -> int:
        """统计指定窗口内某资源的已消耗量。

        登录用户按 user_id 匹配；匿名用户按 anonymous_key 匹配。
        """
        if user_id is None and anonymous_key is None:
            raise ValueError("需要 user_id 或 anonymous_key")

        query = select(func.coalesce(func.sum(UsageEvent.amount), 0)).where(
            UsageEvent.resource == resource,
            UsageEvent.created_at >= window_start,
            UsageEvent.created_at < window_end,
        )
        if user_id is not None:
            query = query.where(UsageEvent.user_id == user_id)
        else:
            query = query.where(UsageEvent.anonymous_key == anonymous_key)

        result = await self.session.execute(query)
        return int(result.scalar() or 0)

    async def migrate_anonymous_to_user(
        self,
        anonymous_key: str,
        user_id: str,
    ) -> int:
        """把匿名 key 名下的 usage_events 迁移到新 user_id。

        注册成功时调用，让用户未登录时用过的次数不浪费。
        返回迁移的行数。
        """
        result = await self.session.execute(
            select(UsageEvent).where(
                UsageEvent.anonymous_key == anonymous_key,
                UsageEvent.user_id.is_(None),
            )
        )
        events = list(result.scalars().all())
        for event in events:
            event.user_id = user_id
            event.anonymous_key = None
        await self.session.flush()
        return len(events)
