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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .orm_models import (
    AgentOutput,
    AgentPhase,
    AnalysisSession,
    RatingReport,
    SessionStatus,
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
    ) -> User:
        """
        创建用户

        Args:
            username: 用户名
            email: 邮箱
            hashed_password: 加密后的密码
            role: 用户角色

        Returns:
            创建的用户对象
        """
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            role=role,
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
