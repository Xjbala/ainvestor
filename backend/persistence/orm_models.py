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
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
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


class SubscriptionStatus(str, PyEnum):
    """订阅状态"""
    ACTIVE = "active"        # 生效中
    PAST_DUE = "past_due"    # 逾期（预留，支付网关接入后用）
    CANCELED = "canceled"    # 已取消（到期后不再续）
    EXPIRED = "expired"      # 已过期


class QuotaResource(str, PyEnum):
    """配额计量资源类型"""
    AI_ANALYSIS = "ai_analysis"            # AI 多 Agent 分析
    EXPERT_VALUATION = "expert_valuation"  # 专家模式估值
    DATA_API = "data_api"                  # 数据服务 API（阶段 C）


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


# ============================================================
# 订阅与配额模型
# ============================================================

class Plan(Base):
    """订阅计划目录。

    由 bootstrap_plans 脚本幂等创建。新增计划不影响历史订阅——
    subscription 仅引用 plan_code，额度以订阅窗口内 grant 为准。
    """
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        comment="计划代码 (free/pro/enterprise)",
    )
    name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="计划名称",
    )
    ai_quota_monthly: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="月度 AI 分析次数配额",
    )
    expert_quota_monthly: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="月度专家估值次数配额",
    )
    data_api_quota_monthly: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="月度数据 API 调用次数配额（阶段 C）",
    )
    price_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="价格（分），free 为 0",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否在售",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="展示排序",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    subscriptions: Mapped[List["Subscription"]] = relationship(
        back_populates="plan"
    )
    grants: Mapped[List["QuotaGrant"]] = relationship(
        back_populates="plan"
    )

    def __repr__(self) -> str:
        return f"<Plan(code={self.code}, name={self.name})>"


class Subscription(Base):
    """用户订阅状态。

    admin 手动开通时插一行；续期 = 把 current_period_end 推后 +
    新建一行 QuotaGrant。一行用户同时只允许一条 active 状态订阅
    （通过 (user_id, status=active) 唯一约束保证，由 service 层维护）。
    """
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("plans.code"),
        nullable=False,
        comment="订阅计划",
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
        index=True,
        comment="订阅状态",
    )
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="当前周期开始时间",
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="当前周期结束时间",
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否在到期后取消",
    )
    activated_by_admin_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="开通该订阅的管理员",
    )
    note: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="管理员备注",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        foreign_keys=[user_id],
        backref="subscriptions",
    )
    plan: Mapped["Plan"] = relationship(back_populates="subscriptions")

    __table_args__ = (
        Index("idx_subscription_user_active", "user_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, user_id={self.user_id}, plan={self.plan_code}, status={self.status})>"


class QuotaGrant(Base):
    """订阅窗口内发放的额度。

    append-only：续期/升级时插新行，不改旧行。
    当前窗口的可用额度 = grant.ai_quota − SUM(usage_events WHERE created_at IN [period_start, period_end])。
    匿名用户无 grant，使用环境变量兜底额度。
    """
    __tablename__ = "quota_grants"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("plans.code"),
        nullable=False,
        comment="发放该额度的计划",
    )
    period_start: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
    )
    ai_quota: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    expert_quota: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    data_api_quota: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="数据 API 配额（阶段 C）",
    )
    source_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        comment="来源订阅",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    plan: Mapped["Plan"] = relationship(back_populates="grants")

    __table_args__ = (
        Index("idx_grant_user_period", "user_id", "period_end"),
    )

    def __repr__(self) -> str:
        return f"<QuotaGrant(id={self.id}, user_id={self.user_id}, plan={self.plan_code})>"


class UsageEvent(Base):
    """配额计量事件流（append-only）。

    登录用户：user_id 非空，anonymous_key 为空。
    匿名用户：user_id 为空，anonymous_key 为 cookie UUID。
    注册时把该 anonymous_key 名下的事件一次性迁移到新 user_id（配额迁移）。
    """
    __tablename__ = "usage_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="登录用户ID，匿名为空",
    )
    anonymous_key: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="匿名 cookie UUID（哈希后存储）",
    )
    ip_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="IP 哈希，用于防刷统计",
    )
    resource: Mapped[QuotaResource] = mapped_column(
        Enum(QuotaResource),
        nullable=False,
        index=True,
        comment="资源类型",
    )
    amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="消耗量",
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("analysis_sessions.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联分析会话（如适用）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_usage_user_resource_time", "user_id", "resource", "created_at"),
        Index("idx_usage_anon_resource_time", "anonymous_key", "resource", "created_at"),
    )

    def __repr__(self) -> str:
        ident = self.user_id or f"anon:{self.anonymous_key}"
        return f"<UsageEvent(id={self.id}, ident={ident}, resource={self.resource}, amount={self.amount})>"
