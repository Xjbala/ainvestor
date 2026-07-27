# -*- coding: utf-8 -*-
"""
将 qualitative_reports 长文本列从 TEXT 升级为 MEDIUMTEXT。

背景：年报 MinerU Markdown 常超过 MySQL TEXT 上限（65535 字节），
导致 management_discussion 等字段 Data too long (1406)。
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

COLUMNS = [
    "overview",
    "revenue_analysis",
    "cost_analysis",
    "rd_investment",
    "core_competencies",
    "risk_factors",
    "future_outlook",
    "capacity_plans",
    "management_discussion",
]


async def migrate():
    async with engine.begin() as conn:
        result = await conn.execute(text("SHOW COLUMNS FROM qualitative_reports"))
        rows = result.fetchall()
        if not rows:
            print("qualitative_reports 表不存在，跳过")
            return

        col_types = {r[0]: str(r[1]).lower() for r in rows}
        print("当前列类型:")
        for c in COLUMNS:
            print(f"  {c}: {col_types.get(c, '(missing)')}")

        for col in COLUMNS:
            ctype = col_types.get(col, "")
            if not ctype:
                print(f"跳过缺失列: {col}")
                continue
            if "mediumtext" in ctype or "longtext" in ctype:
                print(f"已是 medium/longtext，跳过: {col}")
                continue
            print(f"ALTER {col} → MEDIUMTEXT ...")
            await conn.execute(text(
                f"ALTER TABLE qualitative_reports "
                f"MODIFY COLUMN `{col}` MEDIUMTEXT NULL"
            ))
            print(f"  ✓ {col}")

        print("迁移完成")


async def main():
    print("开始迁移 qualitative_reports → MEDIUMTEXT")
    print("-" * 50)
    try:
        await migrate()
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        raise
    print("-" * 50)


if __name__ == "__main__":
    asyncio.run(main())
