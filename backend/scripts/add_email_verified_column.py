# -*- coding: utf-8 -*-
"""
添加 email_verified 字段到 users 表

为已有 users 表增加 email_verified 列，默认 False。
新表由 create_all 自动创建此列，此脚本仅用于已有库的迁移。
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from sqlalchemy import text

from backend.persistence.db import engine

load_dotenv()


async def add_email_verified_column() -> None:
    async with engine.begin() as conn:
        dialect = conn.dialect.name

        if dialect == "mysql":
            result = await conn.execute(
                text("SHOW COLUMNS FROM users LIKE 'email_verified'")
            )
            if result.fetchone():
                print("email_verified 列已存在，无需添加")
                return

            print("正在添加 email_verified 列到 users 表...")
            await conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 0 "
                    "AFTER is_active"
                )
            )
            print("✓ email_verified 列添加成功")

        elif dialect == "sqlite":
            result = await conn.execute(
                text("PRAGMA table_info(users)")
            )
            columns = [row[1] for row in result.fetchall()]
            if "email_verified" in columns:
                print("email_verified 列已存在，无需添加")
                return

            print("正在添加 email_verified 列到 users 表...")
            await conn.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 0"
                )
            )
            print("✓ email_verified 列添加成功")
        else:
            print(f"未支持的数据库方言: {dialect}，请手动添加 email_verified 列")


async def main() -> None:
    print("开始数据库迁移...")
    print("-" * 50)
    await add_email_verified_column()
    print("-" * 50)
    print("迁移完成！")


if __name__ == "__main__":
    asyncio.run(main())
