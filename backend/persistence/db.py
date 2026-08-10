# -*- coding: utf-8 -*-
"""
数据库配置和连接管理

支持 MySQL 作为主数据库，提供统一的异步数据库访问层。
使用 SQLAlchemy 2.0 异步模式。
"""

import os
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# 确保在读取环境变量前加载 .env 文件
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)

# ============================================================
# 数据库配置
# ============================================================

# 从环境变量读取数据库连接 URL
# 格式: mysql+aiomysql://user:password@host:port/database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+aiomysql://root:password@localhost:3306/ainvestor"
)

# 连接池配置
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))

# ============================================================
# SQLAlchemy 引擎和会话
# ============================================================

# 创建异步引擎
# 注意：aiomysql 0.3.x 与 SQLAlchemy pool_pre_ping 存在兼容问题
# (AsyncAdapt_aiomysql_connection.ping 缺少 reconnect 参数)，
# 因此关闭 pre_ping，改用较短的 pool_recycle 回收空闲连接。
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DB_ECHO", "false").lower() == "true",  # 开发时可开启 SQL 日志
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_recycle=min(POOL_RECYCLE, 1800),
    pool_pre_ping=False,
)

# 创建异步会话工厂
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ============================================================
# 模型基类
# ============================================================

class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass


# ============================================================
# 依赖注入
# ============================================================

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话（用于 FastAPI 依赖注入）

    Usage:
        @app.get("/example")
        async def example(session: AsyncSession = Depends(get_db_session)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============================================================
# 数据库生命周期管理
# ============================================================

async def init_database() -> None:
    """
    初始化数据库（创建所有表）

    在应用启动时调用：
        @app.on_event("startup")
        async def startup():
            await init_database()
    """
    # 确保财务/分部等模型注册到 Base.metadata
    from . import orm_models  # noqa: F401
    from . import financial_models  # noqa: F401

    import logging
    _logger = logging.getLogger(__name__)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        # 历史库可能存在不兼容约束（如 JSON 唯一索引），全量 create_all 会失败。
        # 记录完整错误后，尝试仅确保新增关键表存在。
        _logger.error("全量 create_all 失败，尝试仅创建关键表: %s", e, exc_info=True)
        from .financial_models import FinancialCoverageSnapshot

        try:
            async with engine.begin() as conn:
                await conn.run_sync(
                    lambda sync_conn: FinancialCoverageSnapshot.__table__.create(
                        sync_conn, checkfirst=True
                    )
                )
            _logger.warning("全量 create_all 失败，仅创建了关键表；请检查数据库约束")
        except Exception as fallback_err:
            _logger.error("关键表创建也失败: %s", fallback_err, exc_info=True)
            raise


async def close_database() -> None:
    """
    关闭数据库连接池

    在应用关闭时调用：
        @app.on_event("shutdown")
        async def shutdown():
            await close_database()
    """
    await engine.dispose()
