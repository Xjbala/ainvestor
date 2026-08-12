# -*- coding: utf-8 -*-
"""修复旧部署中 analysis_sessions.status 未包含 cancelled 的枚举定义。"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from backend.persistence.db import engine


async def migrate() -> None:
    """为旧 MySQL 数据库的会话状态枚举补充 cancelled。"""
    async with engine.begin() as conn:
        if conn.dialect.name != "mysql":
            print("当前数据库不是 MySQL，无需执行会话状态枚举迁移")
            return

        result = await conn.execute(
            text("SHOW COLUMNS FROM analysis_sessions LIKE 'status'"),
        )
        row = result.mappings().first()
        if not row:
            print("analysis_sessions.status 列不存在，跳过")
            return

        column_type = str(row["Type"]).lower()
        if not column_type.startswith("enum("):
            print("analysis_sessions.status 不是 ENUM，无需迁移")
            return
        if "'cancelled'" in column_type:
            print("analysis_sessions.status 已支持 cancelled，无需迁移")
            return

        await conn.execute(text(
            "ALTER TABLE analysis_sessions MODIFY COLUMN status "
            "ENUM('pending', 'running', 'completed', 'failed', 'cancelled') "
            "NOT NULL DEFAULT 'pending'",
        ))
        print("analysis_sessions.status 已添加 cancelled")


if __name__ == "__main__":
    asyncio.run(migrate())
