import os
import sys

# Force reload environment variables
if 'DATABASE_URL' in os.environ:
    del os.environ['DATABASE_URL']

from dotenv import load_dotenv
load_dotenv('/Users/aceplus/devlop/llm/ainvestor/.env')

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine
from backend.persistence.financial_models import Base
from datetime import date
from decimal import Decimal

def init_financial_tables():
    """初始化财务数据表和测试数据"""
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/ainvestor.db")
    # Convert async URL to sync URL for table creation
    sync_db_url = db_url.replace("+aiosqlite", "")
    
    print(f"Using database: {sync_db_url}")
    
    # Create synchronous engine
    engine = create_engine(sync_db_url)
    
    # Create all tables
    print("Creating financial data tables...")
    Base.metadata.create_all(engine)
    print("Tables created successfully!")
    
    # Insert test data
    from sqlalchemy.orm import Session
    from backend.persistence.financial_models import (
        Company, Exchange, Industry, AccountCategory, ReportType
    )
    
    with Session(engine) as session:
        # 1. Create Exchanges
        print("\nInitializing exchanges...")
        exchanges = [
            Exchange(code="SSE", name="上海证券交易所", country="中国"),
            Exchange(code="SZSE", name="深圳证券交易所", country="中国"),
        ]
        
        for ex in exchanges:
            existing = session.query(Exchange).filter(Exchange.code == ex.code).first()
            if not existing:
                session.add(ex)
                print(f"  Added: {ex.name}")
        
        session.commit()
        session.flush()  # Flush to get IDs
        
        # 2. Create Industries
        print("\nInitializing industries...")
        industries = [
            Industry(code="IND_BANK", name="银行", level=1),
            Industry(code="IND_TECH", name="计算机、通信和其他电子设备制造业", level=1),
        ]
        
        for ind in industries:
            existing = session.query(Industry).filter(Industry.code == ind.code).first()
            if not existing:
                session.add(ind)
                print(f"  Added: {ind.name}")
        
        session.commit()
        session.flush()
        
        # 3. Create Test Company (平安银行 000001)
        print("\nInitializing test company...")
        exchange = session.query(Exchange).filter(Exchange.code == "SZSE").first()
        industry = session.query(Industry).filter(Industry.code == "IND_BANK").first()
        
        if exchange:
            company = session.query(Company).filter(Company.stock_code == "000001").first()
            
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
        categories = [
            AccountCategory(code="A", name="资产", report_type=ReportType.BS, level=1),
            AccountCategory(code="L", name="负债", report_type=ReportType.BS, level=1),
            AccountCategory(code="E", name="所有者权益", report_type=ReportType.BS, level=1),
            AccountCategory(code="I", name="收入", report_type=ReportType.IS, level=1),
            AccountCategory(code="C", name="成本", report_type=ReportType.IS, level=1),
        ]
        
        for cat in categories:
            existing = session.query(AccountCategory).filter(AccountCategory.code == cat.code).first()
            if not existing:
                session.add(cat)
                print(f"  Added: {cat.name}")
        
        session.commit()
        
        print("\nInitialization completed successfully!")
        print("\nTest data:")
        print("- Exchange: 上海证券交易所 (SSE), 深圳证券交易所 (SZSE)")
        print("- Industry: 银行, 计算机、通信和其他电子设备制造业")
        print("- Company: 000001 平安银行 (平安银行股份有限公司)")

if __name__ == "__main__":
    init_financial_tables()