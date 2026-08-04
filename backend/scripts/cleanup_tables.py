import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.persistence.db import engine, Base
from backend.persistence.financial_models import AccountCategory, AccountSubject

async def cleanup_tables():
    async with engine.begin() as conn:
        print("正在由于外键约束暂时关闭检查并删除旧表...")
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        
        tables = [
            "financial_match_issues",
            "financial_data",
            "account_subject_source_aliases",
            "account_subjects",
            "account_categories"
        ]
        
        for table in tables:
            await conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
            print(f"已删除表: {table}")
            
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        print("旧表删除完成。")

if __name__ == "__main__":
    from sqlalchemy import text
    asyncio.run(cleanup_tables())
