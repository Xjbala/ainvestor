# -*- coding: utf-8 -*-
"""
持久化层

提供数据库访问和 ORM 模型。

模块结构:
- db.py: 数据库连接和会话管理
- orm_models.py: SQLAlchemy ORM 模型定义
- repository.py: 数据访问仓库
- models.py: 兼容性 dataclass 模型（将逐步废弃）
- database.py: 原 SQLite 实现（将逐步废弃）
"""

# 新的 MySQL/ORM 实现
from .db import (
    Base,
    async_session_factory,
    close_database,
    engine,
    get_db_session,
    init_database,
)
from .orm_models import (
    AgentOutput,
    AgentPhase,
    AnalysisSession,
    RatingReport,
    SessionStatus,
    User,
    UserRole,
)
from .repository import (
    AgentOutputRepository,
    ReportRepository,
    SessionRepository,
    UserRepository,
)

__all__ = [
    # 数据库连接
    "Base",
    "engine",
    "async_session_factory",
    "get_db_session",
    "init_database",
    "close_database",
    # ORM 模型
    "User",
    "UserRole",
    "AnalysisSession",
    "SessionStatus",
    "AgentOutput",
    "AgentPhase",
    "RatingReport",
    # 仓库
    "UserRepository",
    "SessionRepository",
    "AgentOutputRepository",
    "ReportRepository",
]
