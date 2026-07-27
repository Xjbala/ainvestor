# -*- coding: utf-8 -*-
"""
扩展 crawler_tasks.data_type 枚举，支持定性年报/新闻采集。

旧库可能只有：
  COMPANY_LIST, BALANCE_SHEET, INCOME_STATEMENT, CASH_FLOW,
  STOCK_PRICE, BATCH_FINANCIAL_DATA

本脚本补充：
  QUALITATIVE_REPORT, NEWS_SENTIMENT
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


async def migrate():
    """扩展 data_type 枚举列。"""
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SHOW COLUMNS FROM crawler_tasks LIKE 'data_type'"
        ))
        row = result.fetchone()
        if not row:
            print("crawler_tasks.data_type 列不存在，跳过")
            return

        col_type = str(row[1]).upper()
        print(f"当前 data_type: {row[1]}")

        needed = ("QUALITATIVE_REPORT", "NEWS_SENTIMENT")
        if all(n in col_type for n in needed):
            print("data_type 枚举已包含定性/新闻类型，无需迁移")
            return

        print("正在扩展 data_type 枚举...")
        await conn.execute(text(
            """
            ALTER TABLE crawler_tasks
            MODIFY COLUMN data_type ENUM(
                'COMPANY_LIST','BALANCE_SHEET','INCOME_STATEMENT','CASH_FLOW',
                'STOCK_PRICE','BATCH_FINANCIAL_DATA',
                'QUALITATIVE_REPORT','NEWS_SENTIMENT'
            ) NOT NULL
            """
        ))
        print("✓ data_type 枚举扩展成功")


async def main():
    print("开始迁移 crawler_tasks.data_type ...")
    print("-" * 50)
    try:
        await migrate()
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        raise
    print("-" * 50)
    print("迁移完成")


if __name__ == "__main__":
    asyncio.run(main())
