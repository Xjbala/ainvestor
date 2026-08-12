# -*- coding: utf-8 -*-
"""
数据库兼容层

提供从旧 SQLite 接口到新 MySQL/ORM 接口的适配，
确保现有代码（如 state_sync.py, api/routes.py）无需修改即可工作。

使用方式:
    from backend.persistence.compat import get_database, close_database

此模块为过渡期使用，待所有代码迁移到 Repository 模式后将废弃。
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .db import async_session_factory, init_database, close_database as _close_db
from .orm_models import (
    AgentOutput as AgentOutputORM,
    AgentPhase,
    AnalysisSession as AnalysisSessionORM,
    RatingReport as RatingReportORM,
    SessionStatus,
)

# 兼容旧的 dataclass 模型
from .models import AnalysisSession, AgentOutput, RatingReport

logger = logging.getLogger(__name__)


class CompatDatabase:
    """
    兼容性数据库类

    提供与原 Database 类相同的接口，内部使用新的 ORM 实现。
    """

    def __init__(self):
        self._initialized = False

    async def connect(self):
        """连接数据库（初始化表结构）"""
        if not self._initialized:
            # init_database 内部已有容错：仅在关键表也无法创建时才抛异常
            await init_database()
            self._initialized = True
            logger.info("Database connected (MySQL via SQLAlchemy)")

    async def close(self):
        """关闭数据库连接"""
        await _close_db()
        self._initialized = False
        logger.info("Database connection closed")

    # ========== Session 操作 ==========

    async def create_session(
        self,
        tickers: List[str],
        date: str,
        session_id: Optional[str] = None,
        status: str = "pending",
        mode: str = "ai",
    ) -> AnalysisSession:
        """创建分析会话"""
        async with async_session_factory() as session:
            orm_session = AnalysisSessionORM(
                tickers=json.dumps(tickers),
                date=date,
                status=SessionStatus(status),
                mode=mode,
            )
            if session_id:
                orm_session.id = session_id

            # 如果状态是completed，设置completed_at
            if status == "completed":
                orm_session.completed_at = datetime.now()

            session.add(orm_session)
            await session.commit()
            await session.refresh(orm_session)

            return AnalysisSession(
                id=orm_session.id,
                tickers=orm_session.tickers,
                date=orm_session.date,
                status=orm_session.status.value,
                created_at=orm_session.created_at,
                updated_at=orm_session.updated_at,
                completed_at=orm_session.completed_at,
                mode=orm_session.mode,
            )

    async def update_session_status(self, session_id: str, status: str):
        """更新会话状态"""
        async with async_session_factory() as session:
            result = await session.execute(
                select(AnalysisSessionORM).where(AnalysisSessionORM.id == session_id)
            )
            orm_session = result.scalar_one_or_none()

            if orm_session:
                orm_session.status = SessionStatus(status)
                if status in ("completed", "failed", "cancelled"):
                    orm_session.completed_at = datetime.now()
                await session.commit()

    async def get_session(self, session_id: str) -> Optional[AnalysisSession]:
        """获取会话"""
        async with async_session_factory() as session:
            result = await session.execute(
                select(AnalysisSessionORM).where(AnalysisSessionORM.id == session_id)
            )
            orm_session = result.scalar_one_or_none()

            if orm_session:
                return AnalysisSession(
                    id=orm_session.id,
                    tickers=orm_session.tickers,
                    date=orm_session.date,
                    status=orm_session.status.value,
                    created_at=orm_session.created_at,
                    updated_at=orm_session.updated_at,
                    completed_at=orm_session.completed_at,
                    mode=getattr(orm_session, 'mode', 'ai')
                )
            return None

    async def get_recent_sessions(self, limit: int = 10) -> List[AnalysisSession]:
        """获取最近的会话"""
        async with async_session_factory() as session:
            result = await session.execute(
                select(AnalysisSessionORM)
                .order_by(AnalysisSessionORM.created_at.desc())
                .limit(limit)
            )
            sessions = []
            for orm_session in result.scalars().all():
                sessions.append(AnalysisSession(
                    id=orm_session.id,
                    tickers=orm_session.tickers,
                    date=orm_session.date,
                    status=orm_session.status.value,
                    created_at=orm_session.created_at,
                    updated_at=orm_session.updated_at,
                    completed_at=orm_session.completed_at,
                    mode=getattr(orm_session, 'mode', 'ai')
                ))
            return sessions

    async def delete_session(self, session_id: str) -> bool:
        """删除已结束的分析会话及其输出和报告。"""
        async with async_session_factory() as session:
            result = await session.execute(
                select(AnalysisSessionORM)
                .where(AnalysisSessionORM.id == session_id)
                .options(
                    selectinload(AnalysisSessionORM.outputs),
                    selectinload(AnalysisSessionORM.report),
                )
            )
            orm_session = result.scalar_one_or_none()
            if not orm_session:
                return False
            if orm_session.status in (SessionStatus.PENDING, SessionStatus.RUNNING):
                raise ValueError("正在运行的分析会话不能删除")

            await session.delete(orm_session)
            await session.commit()
            return True

    # ========== Agent Output 操作 ==========

    async def save_agent_output(
        self,
        session_id: str,
        agent_id: str,
        agent_type: str,
        phase: str,
        content: str,
    ) -> AgentOutput:
        """保存Agent输出"""
        # 兼容扩展 phase；未知值回落到 analysis，避免 MySQL ENUM 写入失败
        phase_aliases = {
            "analysis": AgentPhase.ANALYSIS,
            "conference": AgentPhase.CONFERENCE,
            "prediction": AgentPhase.PREDICTION,
            "risk_assessment": AgentPhase.ANALYSIS,
            "investment_recommendation": AgentPhase.PREDICTION,
        }
        try:
            phase_enum = phase_aliases.get(phase) or AgentPhase(phase)
        except Exception:
            phase_enum = AgentPhase.ANALYSIS

        content_text = content if isinstance(content, str) else str(content or "")

        async with async_session_factory() as session:
            orm_output = AgentOutputORM(
                session_id=session_id,
                agent_id=agent_id,
                agent_type=agent_type,
                phase=phase_enum,
                content=content_text,
            )
            session.add(orm_output)
            await session.commit()
            await session.refresh(orm_output)

            return AgentOutput(
                id=orm_output.id,
                session_id=orm_output.session_id,
                agent_id=orm_output.agent_id,
                agent_type=orm_output.agent_type,
                phase=orm_output.phase.value,
                content=orm_output.content,
                created_at=orm_output.created_at,
            )

    async def get_session_outputs(self, session_id: str) -> List[AgentOutput]:
        """获取会话的所有Agent输出"""
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentOutputORM)
                .where(AgentOutputORM.session_id == session_id)
                .order_by(AgentOutputORM.created_at.asc())
            )
            outputs = []
            for orm_output in result.scalars().all():
                outputs.append(AgentOutput(
                    id=orm_output.id,
                    session_id=orm_output.session_id,
                    agent_id=orm_output.agent_id,
                    agent_type=orm_output.agent_type,
                    phase=orm_output.phase.value,
                    content=orm_output.content,
                    created_at=orm_output.created_at,
                ))
            return outputs

    # ========== Rating Report 操作 ==========

    async def save_report(
        self,
        session_id: str,
        report_content: str,
        recommendations: Optional[dict] = None,
    ) -> RatingReport:
        """保存评级报告"""
        # 确保 recommendations 可 JSON 序列化（Msg/content 块等需兜底）
        rec_text: Optional[str] = None
        if recommendations is not None:
            try:
                rec_text = json.dumps(recommendations, ensure_ascii=False, default=str)
            except Exception:
                rec_text = json.dumps({"raw": str(recommendations)}, ensure_ascii=False)

        async with async_session_factory() as session:
            # 检查是否已存在
            result = await session.execute(
                select(RatingReportORM).where(RatingReportORM.session_id == session_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.report_content = report_content
                existing.recommendations = rec_text
                await session.commit()
                orm_report = existing
            else:
                orm_report = RatingReportORM(
                    session_id=session_id,
                    report_content=report_content,
                    recommendations=rec_text,
                )
                session.add(orm_report)
                await session.commit()
                await session.refresh(orm_report)

            return RatingReport(
                id=orm_report.id,
                session_id=orm_report.session_id,
                report_content=orm_report.report_content,
                recommendations=orm_report.recommendations or "",
                created_at=orm_report.created_at,
            )

    async def get_report(self, session_id: str) -> Optional[RatingReport]:
        """获取评级报告"""
        async with async_session_factory() as session:
            result = await session.execute(
                select(RatingReportORM).where(RatingReportORM.session_id == session_id)
            )
            orm_report = result.scalar_one_or_none()

            if orm_report:
                return RatingReport(
                    id=orm_report.id,
                    session_id=orm_report.session_id,
                    report_content=orm_report.report_content,
                    recommendations=orm_report.recommendations or "",
                    created_at=orm_report.created_at,
                )
            return None


# ============================================================
# 全局实例（兼容原接口）
# ============================================================

_db: Optional[CompatDatabase] = None


async def get_database() -> CompatDatabase:
    """获取数据库实例（兼容原接口）"""
    global _db
    if _db is None:
        _db = CompatDatabase()
        await _db.connect()
    return _db


async def close_database():
    """关闭数据库连接（兼容原接口）"""
    global _db
    if _db:
        await _db.close()
        _db = None
