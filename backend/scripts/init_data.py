import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.persistence.db import async_session_factory
from backend.persistence.financial_models import DataSource, DataSourceType, Exchange
from sqlalchemy import select, text

async def init_data():
    async with async_session_factory() as session:
        print("Initializing data sources...")
        
        # 1. Initialize Data Sources
        sources = [
            {
                "code": "sina",
                "name": "新浪财经",
                "base_url": "https://finance.sina.com.cn",
                "api_type": DataSourceType.HTML,
                "created_at": "2023-01-01 00:00:00"
            },
            {
                "code": "exchange_api",
                "name": "交易所官网",
                "base_url": "", 
                "api_type": DataSourceType.JSON,
                "created_at": "2023-01-01 00:00:00"
            },
            {
                "code": "cninfo",
                "name": "巨潮资讯网",
                "base_url": "http://www.cninfo.com.cn",
                "api_type": DataSourceType.HTML,
                "created_at": "2023-01-01 00:00:00"
            },
            {
                "code": "sina_news",
                "name": "新浪财经新闻",
                "base_url": "https://finance.sina.com.cn",
                "api_type": DataSourceType.HTML,
                "created_at": "2023-01-01 00:00:00"
            }
        ]

        for s in sources:
            result = await session.execute(
                text("SELECT * FROM data_sources WHERE code = :code"),
                {"code": s["code"]}
            )
            if not result.first():
                print(f"Adding data source: {s['name']}")
                new_source = DataSource(
                    code=s["code"],
                    name=s["name"],
                    base_url=s["base_url"],
                    api_type=s["api_type"]
                )
                session.add(new_source)
            else:
                print(f"Data source {s['name']} already exists.")

        # 2. Initialize Exchanges
        print("\nInitializing exchanges...")
        exchanges = [
            {
                "code": "SSE",
                "name": "上海证券交易所",
                "country": "中国"
            },
            {
                "code": "SZSE",
                "name": "深圳证券交易所",
                "country": "中国"
            },
            {
                "code": "BSE",
                "name": "北京证券交易所",
                "country": "中国"
            }
        ]

        for e in exchanges:
             # Check using direct SQL for simplicity or ORM query
            from sqlalchemy import select
            result = await session.execute(select(Exchange).where(Exchange.code == e["code"]))
            if not result.scalar_one_or_none():
                print(f"Adding exchange: {e['name']}")
                new_exchange = Exchange(
                    code=e["code"],
                    name=e["name"],
                    country=e["country"]
                )
                session.add(new_exchange)
            else:
                print(f"Exchange {e['name']} already exists.")

        await session.commit()
        print("\nInitialization completed successfully!")

if __name__ == "__main__":
    asyncio.run(init_data())
