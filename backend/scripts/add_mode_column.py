# -*- coding: utf-8 -*-
"""
添加mode字段到analysis_sessions表
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.persistence.db import async_session_factory, engine

load_dotenv()


async def add_mode_column():
    """添加mode列到analysis_sessions表"""
    async with engine.begin() as conn:
        try:
            # 检查列是否已存在
            result = await conn.execute(text(
                "SHOW COLUMNS FROM analysis_sessions LIKE 'mode'"
            ))
            if result.fetchone():
                print("mode列已存在，无需添加")
                return

            # 添加mode列
            print("正在添加mode列到analysis_sessions表...")
            await conn.execute(text(
                "ALTER TABLE analysis_sessions "
                "ADD COLUMN mode VARCHAR(20) NOT NULL DEFAULT 'ai' "
                "AFTER status"
            ))
            print("✓ mode列添加成功")

            # 添加索引
            print("正在添加mode列索引...")
            await conn.execute(text(
                "CREATE INDEX idx_session_mode ON analysis_sessions(mode)"
            ))
            print("✓ 索引创建成功")

            # 更新现有专家模式的记录
            print("正在更新现有专家模式记录...")
            await conn.execute(text(
                "UPDATE analysis_sessions "
                "SET mode = 'expert' "
                "WHERE status = 'completed' "
                "AND id NOT IN (SELECT session_id FROM agent_outputs WHERE phase = 'conference')"
            ))
            result = await conn.execute(text("SELECT ROW_COUNT()"))
            updated = result.scalar()
            print(f"✓ 更新了 {updated} 条专家模式记录")

            print("\n数据库迁移完成！")

        except Exception as e:
            print(f"❌ 迁移失败: {e}")
            raise


async def main():
    """主函数"""
    print("开始数据库迁移...")
    print("-" * 50)
    await add_mode_column()
    print("-" * 50)
    print("迁移完成！")


if __name__ == "__main__":
    asyncio.run(main())