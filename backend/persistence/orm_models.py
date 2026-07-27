# -*- coding: utf-8 -*-
"""
ORM 模型定义

使用 SQLAlchemy 2.0 声明式模型，支持 MySQL 数据库。
所有模型继承自 Base，自动映射到数据库表。
"""

import json
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


# ============================================================
# 枚举类型
# ============================================================

class SessionStatus(str, PyEnum):
    """分析会话状态"""
    PENDING = "pending"      # 待处理
    RUNNING = "running"      # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


class AgentPhase(str, PyEnum):
    """Agent 执行阶段"""
    ANALYSIS = "analysis"      # 分析阶段
    CONFERENCE = "conference"  # 会议讨论阶段
    PREDICTION = "prediction"  # 预测阶段
    # 兼容扩展阶段名（历史/调用侧可能直接传入）
    RISK_ASSESSMENT = "risk_assessment"
    INVESTMENT_RECOMMENDATION = "investment_recommendation"


class UserRole(str, PyEnum):
    """用户角色"""
    USER = "user"            # 普通用户
    EXPERT = "expert"        # 专家用户
    ADMIN = "admin"          # 管理员
    SUPERADMIN = "superadmin"  # 超级管理员


# ============================================================
# 用户模型（阶段 1 实现）
# ============================================================

class User(Base):
    """
    用户表

    存储系统用户信息，支持多角色权限控制。
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="用户唯一标识"
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="用户名"
    )
    email: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        comment="邮箱地址"
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="加密后的密码"
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        default=UserRole.USER,
        nullable=False,
        comment="用户角色"
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="账户是否激活"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间"
    )

    # 关联关系
    sessions: Mapped[List["AnalysisSession"]] = relationship(
        back_populates="user",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"


# ============================================================
# 分析会话模型
# ============================================================

class AnalysisSession(Base):
    """
    分析会话表

    记录每次投资分析的会话信息，包括股票代码、分析日期、状态等。
    """
    __tablename__ = "analysis_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="会话唯一标识"
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="所属用户ID"
    )
    tickers: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="股票代码列表(JSON数组)"
    )
    date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="分析日期(YYYY-MM-DD)"
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus),
        default=SessionStatus.PENDING,
        nullable=False,
        index=True,
        comment="会话状态"
    )
    mode: Mapped[str] = mapped_column(
        String(20),
        default="ai",
        nullable=False,
        comment="分析模式(ai/expert)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="完成时间"
    )

    # 关联关系
    user: Mapped[Optional["User"]] = relationship(back_populates="sessions")
    outputs: Mapped[List["AgentOutput"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    report: Mapped[Optional["RatingReport"]] = relationship(
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("idx_session_user_status", "user_id", "status"),
        Index("idx_session_created", "created_at"),
    )

    @property
    def tickers_list(self) -> List[str]:
        """获取股票代码列表"""
        return json.loads(self.tickers) if self.tickers else []

    def __repr__(self) -> str:
        return f"<AnalysisSession(id={self.id}, tickers={self.tickers}, status={self.status})>"


# ============================================================
# Agent 输出模型
# ============================================================

class AgentOutput(Base):
    """
    Agent 输出表

    记录各个 AI Agent 在分析过程中的输出内容。
    """
    __tablename__ = "agent_outputs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="输出记录唯一标识"
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话ID"
    )
    agent_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Agent标识符"
    )
    agent_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Agent类型(analyst/risk_manager/portfolio_manager)"
    )
    phase: Mapped[AgentPhase] = mapped_column(
        Enum(AgentPhase),
        nullable=False,
        comment="执行阶段"
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="输出内容"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="创建时间"
    )

    # 关联关系
    session: Mapped["AnalysisSession"] = relationship(back_populates="outputs")

    # 索引
    __table_args__ = (
        Index("idx_output_session_phase", "session_id", "phase"),
    )

    def __repr__(self) -> str:
        return f"<AgentOutput(id={self.id}, agent_id={self.agent_id}, phase={self.phase})>"


# ============================================================
# 评级报告模型
# ============================================================

class RatingReport(Base):
    """
    评级报告表

    存储最终的投资评级报告内容。
    """
    __tablename__ = "rating_reports"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="报告唯一标识"
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="所属会话ID"
    )
    report_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="报告内容(Markdown格式)"
    )
    recommendations: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="投资建议(JSON格式)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="创建时间"
    )

    # 关联关系
    session: Mapped["AnalysisSession"] = relationship(back_populates="report")

    @property
    def recommendations_dict(self) -> dict:
        """获取投资建议字典"""
        return json.loads(self.recommendations) if self.recommendations else {}

    def __repr__(self) -> str:
        return f"<RatingReport(id={self.id}, session_id={self.session_id})>"
