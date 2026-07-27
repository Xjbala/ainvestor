import asyncio
import sys
import os
from decimal import Decimal
from datetime import date

# Force reload environment variables
if 'DATABASE_URL' in os.environ:
    del os.environ['DATABASE_URL']

from dotenv import load_dotenv
load_dotenv('/Users/aceplus/devlop/llm/ainvestor/.env')

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.persistence.db import engine, async_session_factory
from backend.persistence.financial_models import (
    Company, Exchange, Industry, AccountCategory, AccountSubject
)

async def init_financial_tables():
    """初始化财务数据表和测试数据"""
    print("Creating financial data tables...")
    
    # Create all tables
    from backend.persistence.financial_models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("Tables created successfully!")
    
    # Initialize test data
    async with async_session_factory() as session:
        # 1. Create Exchanges
        print("\nInitializing exchanges...")
        exchanges = [
            Exchange(code="SSE", name="上海证券交易所", country="中国"),
            Exchange(code="SZSE", name="深圳证券交易所", country="中国"),
        ]
        
        for ex in exchanges:
            from sqlalchemy import select
            result = await session.execute(select(Exchange).where(Exchange.code == ex.code))
            if not result.scalar_one_or_none():
                session.add(ex)
                print(f"  Added: {ex.name}")
        
        await session.flush()  # Flush to get IDs
        
        # 2. Create Industries
        print("\nInitializing industries...")
        industries = [
            Industry(code="IND_BANK", name="银行", level=1),
            Industry(code="IND_TECH", name="计算机、通信和其他电子设备制造业", level=1),
        ]
        
        for ind in industries:
            from sqlalchemy import select
            result = await session.execute(select(Industry).where(Industry.code == ind.code))
            if not result.scalar_one_or_none():
                session.add(ind)
                print(f"  Added: {ind.name}")
        
        await session.flush()
        
        # 3. Create Test Company (平安银行 000001)
        print("\nInitializing test company...")
        from sqlalchemy import select
        result = await session.execute(select(Exchange).where(Exchange.code == "SZSE"))
        exchange = result.scalar_one_or_none()
        
        result = await session.execute(select(Industry).where(Industry.code == "IND_BANK"))
        industry = result.scalar_one_or_none()
        
        if exchange:
            result = await session.execute(select(Company).where(Company.stock_code == "000001"))
            company = result.scalar_one_or_none()
            
            if not company:
                company = Company(
                    stock_code="000001",
                    stock_name="平安银行",
                    company_name="平安银行股份有限公司",
                    exchange_id=exchange.id,
                    industry_id=industry.id if industry else None,
                    listing_date=date(1991, 4, 3),
                    current_price=Decimal("10.83"),
                    market_cap=Decimal("21000000"),  # 万
                    pe_ratio=Decimal("5.5"),
                    pb_ratio=Decimal("0.8")
                )
                session.add(company)
                print(f"  Added: {company.display_name}")
            else:
                print(f"  Company already exists: {company.display_name}")
        
        # 4. Create Account Categories
        print("\nInitializing account categories...")
        from backend.persistence.financial_models import ReportType
        categories = [
            AccountCategory(code="A", name="资产", report_type=ReportType.BS, level=1),
            AccountCategory(code="L", name="负债", report_type=ReportType.BS, level=1),
            AccountCategory(code="E", name="所有者权益", report_type=ReportType.BS, level=1),
            AccountCategory(code="I", name="收入", report_type=ReportType.IS, level=1),
            AccountCategory(code="C", name="成本", report_type=ReportType.IS, level=1),
        ]
        
        for cat in categories:
            from sqlalchemy import select
            result = await session.execute(select(AccountCategory).where(AccountCategory.code == cat.code))
            if not result.scalar_one_or_none():
                session.add(cat)
                print(f"  Added: {cat.name}")
        
        await session.commit()
        
        print("\nInitialization completed successfully!")
        print("\nTest data:")
        print("- Exchange: 上海证券交易所 (SSE), 深圳证券交易所 (SZSE)")
        print("- Industry: 银行, 计算机、通信和其他电子设备制造业")
        print("- Company: 000001 平安银行 (平安银行股份有限公司)")

if __name__ == "__main__":
    asyncio.run(init_financial_tables())