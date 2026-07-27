# -*- coding: utf-8 -*-
"""
公司管理 API 路由

提供上市公司基本信息的查询、统计和管理接口。
"""

import logging
from typing import Dict, List, Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from uuid import uuid4

from ..core.dependencies import get_current_user, require_admin, get_current_user_optional
from ..persistence.db import get_db_session
from ..persistence.orm_models import User
from ..persistence.financial_models import (
    Company, Exchange, Industry, CompanyStatus,
    CrawlerTask, CrawlerDataType, CrawlerTaskStatus, DataSource, DataSourceType,
    FinancialData, AccountSubject, ReportType, ReportPeriod,
)
from ..crawler.crawler_engine import crawler_engine
from ..crawler.sina_crawler import SinaCrawlerService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/companies", tags=["公司管理"])


# ============================================================
# 请求/响应模型
# ============================================================

class CompanyBase(BaseModel):
    stock_code: str
    stock_name: str
    company_name: str
    exchange_id: int
    industry_id: Optional[int] = None
    listing_date: Optional[date] = None
    current_price: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    status: str = "active"

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(BaseModel):
    stock_name: Optional[str] = None
    company_name: Optional[str] = None
    exchange_id: Optional[int] = None
    industry_id: Optional[int] = None
    listing_date: Optional[date] = None
    current_price: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    status: Optional[str] = None

class CompanyResponse(CompanyBase):
    exchange_name: Optional[str] = None
    industry_name: Optional[str] = None
    updated_at: str

    class Config:
        from_attributes = True

class PaginatedCompanyResponse(BaseModel):
    items: List[CompanyResponse]
    total: int
    page: int
    page_size: int

class ExchangeStats(BaseModel):
    exchange: str
    count: int

class CompanyStatistics(BaseModel):
    total_count: int
    active_count: int
    exchange_statistics: List[ExchangeStats]


# ============================================================
# 路由实现
# ============================================================

@router.get("", response_model=PaginatedCompanyResponse)
async def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="搜索关键词(代码或名称)"),
    exchange_id: Optional[int] = Query(None, description="交易所ID"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    分页获取公司列表，支持搜索和筛选
    """
    # 构建查询
    query = select(Company).outerjoin(Exchange).outerjoin(Industry)
    
    if search:
        query = query.where(
            or_(
                Company.stock_code.contains(search),
                Company.stock_name.contains(search),
                Company.company_name.contains(search)
            )
        )
    
    if exchange_id:
        query = query.where(Company.exchange_id == exchange_id)
    
    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total = await session.execute(count_query)
    total_count = total.scalar()
    
    # 分页
    query = query.options(joinedload(Company.exchange), joinedload(Company.industry))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    companies = result.scalars().unique().all()
    
    # 转换为响应模型
    items = []
    for c in companies:
        items.append(CompanyResponse(
            stock_code=c.stock_code,
            stock_name=c.stock_name,
            company_name=c.company_name,
            exchange_id=c.exchange_id,
            exchange_name=c.exchange.name if c.exchange else None,
            industry_id=c.industry_id,
            industry_name=c.industry.name if c.industry else None,
            listing_date=c.listing_date,
            current_price=float(c.current_price) if c.current_price else None,
            market_cap=float(c.market_cap) if c.market_cap else None,
            pe_ratio=float(c.pe_ratio) if c.pe_ratio else None,
            pb_ratio=float(c.pb_ratio) if c.pb_ratio else None,
            status=c.status.value,
            updated_at=c.updated_at.isoformat()
        ))
    
    return PaginatedCompanyResponse(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size
    )


@router.get("/statistics", response_model=CompanyStatistics)
async def get_statistics(session: AsyncSession = Depends(get_db_session)):
    """
    获取公司数据统计信息
    """
    # 总数
    total_count = await session.execute(select(func.count(Company.stock_code)))
    total = total_count.scalar()
    
    # 活跃数
    active_count = await session.execute(
        select(func.count(Company.stock_code)).where(Company.status == CompanyStatus.ACTIVE)
    )
    active = active_count.scalar()
    
    # 各交易所统计
    exchange_query = (
        select(Exchange.name, func.count(Company.stock_code))
        .join(Company, Exchange.id == Company.exchange_id)
        .group_by(Exchange.name)
    )
    exchange_res = await session.execute(exchange_query)
    exchange_stats = [
        ExchangeStats(exchange=name, count=count) 
        for name, count in exchange_res.all()
    ]
    
    return CompanyStatistics(
        total_count=total,
        active_count=active,
        exchange_statistics=exchange_stats
    )


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    request: CompanyCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin)
):
    """
    手动新增公司信息
    """
    # 检查是否已存在
    stmt = select(Company).where(Company.stock_code == request.stock_code)
    existing = await session.execute(stmt)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"股票代码 {request.stock_code} 已存在"
        )
    
    company = Company(
        stock_code=request.stock_code,
        stock_name=request.stock_name,
        company_name=request.company_name,
        exchange_id=request.exchange_id,
        industry_id=request.industry_id,
        listing_date=request.listing_date,
        current_price=request.current_price,
        market_cap=request.market_cap,
        pe_ratio=request.pe_ratio,
        pb_ratio=request.pb_ratio,
        status=CompanyStatus(request.status)
    )
    
    session.add(company)
    await session.commit()
    await session.refresh(company)
    
    return _company_to_response(company)


@router.get("/{stock_code}", response_model=CompanyResponse)
async def get_company(
    stock_code: str,
    session: AsyncSession = Depends(get_db_session)
):
    """
    获取单个公司详细信息
    """
    stmt = select(Company).options(
        joinedload(Company.exchange),
        joinedload(Company.industry)
    ).where(Company.stock_code == stock_code)
    result = await session.execute(stmt)
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(status_code=404, detail="未找到公司")
    
    return _company_to_response(company)


@router.put("/{stock_code}", response_model=CompanyResponse)
async def update_company(
    stock_code: str,
    request: CompanyUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin)
):
    """
    更新公司基本信息
    """
    stmt = select(Company).options(
        joinedload(Company.exchange),
        joinedload(Company.industry)
    ).where(Company.stock_code == stock_code)
    result = await session.execute(stmt)
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(status_code=404, detail="未找到公司")
    
    # 更新字段
    for field, value in request.dict(exclude_unset=True).items():
        if field == "status":
            setattr(company, field, CompanyStatus(value))
        else:
            setattr(company, field, value)
            
    await session.commit()
    await session.refresh(company)
    
    return _company_to_response(company)


@router.post("/{stock_code}/refresh", response_model=CompanyResponse)
async def refresh_company_quotes(
    stock_code: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user_optional) # Allow authenticated users
):
    """
    实时更新公司行情信息
    """
    # 1. 检查公司是否存在
    stmt = select(Company).options(
        joinedload(Company.exchange),
        joinedload(Company.industry)
    ).where(Company.stock_code == stock_code)
    result = await session.execute(stmt)
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(status_code=404, detail="未找到公司")
        
    # 2. 调用爬虫服务更新 (使用 SinaCrawlerService)
    # 注意：这里我们临时实例化 Service，理想情况应该使用依赖注入或单例
    # Fix: Use async context manager to initialize client
    
    crawler = SinaCrawlerService(session)
    async with crawler:
        success = await crawler.update_company_quotes(stock_code)
    
    if not success:
        raise HTTPException(status_code=502, detail="更新行情失败，请稍后重试")
        
    # 3. 刷新并返回最新数据
    # 使用 explicit query 替代 refresh，确保关系被 eagerly loaded
    stmt = select(Company).options(
        joinedload(Company.exchange),
        joinedload(Company.industry)
    ).where(Company.stock_code == stock_code)
    result = await session.execute(stmt)
    company = result.scalar_one_or_none()
    
    return _company_to_response(company)


@router.delete("/{stock_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    stock_code: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin)
):
    """
    删除公司记录
    """
    stmt = select(Company).where(Company.stock_code == stock_code)
    result = await session.execute(stmt)
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="公司不存在"
        )
        
    await session.delete(company)
    await session.commit()
    
    return None


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_companies(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    从交易所官方接口同步公司列表
    """
    # 1. 确保数据源存在
    stmt = select(DataSource).where(DataSource.code == "exchange_api")
    result = await session.execute(stmt)
    data_source = result.scalar_one_or_none()
    
    if not data_source:
        data_source = DataSource(
            name="交易所官方API",
            code="exchange_api",
            api_type=DataSourceType.JSON,
            is_active=True,
            rate_limit=60
        )
        session.add(data_source)
        await session.flush()
    
    # 2. 创建同步任务
    task = CrawlerTask(
        id=str(uuid4()),
        task_name="官方交易所数据同步",
        data_source_id=data_source.id,
        data_type=CrawlerDataType.COMPANY_LIST,
        created_by=current_user.id if current_user else None,
        status=CrawlerTaskStatus.PENDING
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    
    # 3. 触发后台执行
    background_tasks.add_task(crawler_engine.execute_task, task.id)
    
    return {
        "message": "同步任务已启动",
        "task_id": task.id
    }


# ============================================================
# 原始财务数据查询
# ============================================================

class FinancialDataItem(BaseModel):
    """单个科目数据"""
    subject_code: str
    subject_name: str
    value: Optional[float] = None

class FinancialDataPeriod(BaseModel):
    """单个报告期的全部科目"""
    report_date: str
    report_period: str
    items: List[FinancialDataItem]

class FinancialDataResponse(BaseModel):
    """财务数据响应"""
    company_code: str
    company_name: str
    report_type: str
    periods: List[FinancialDataPeriod]


@router.get("/{stock_code}/financial-data", response_model=FinancialDataResponse)
async def get_financial_data(
    stock_code: str,
    report_type: str = Query("BS", description="报表类型: BS/IS/CF"),
    years: int = Query(5, ge=1, le=20, description="查询年数"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    获取公司原始财务数据（资产负债表/利润表/现金流量表）

    返回多年对比数据，按报告期分组，每个科目包含代码、名称和数值。
    """
    # 1. 验证公司
    stmt = select(Company).where(Company.stock_code == stock_code)
    result = await session.execute(stmt)
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")

    # 2. 验证报表类型
    try:
        rt = ReportType(report_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的报表类型: {report_type}")

    # 3. 查询财务数据 + 科目名称
    # 只取年报数据（report_period = annual），按 report_date 降序
    stmt = (
        select(FinancialData, AccountSubject.name)
        .outerjoin(AccountSubject, FinancialData.subject_id == AccountSubject.id)
        .where(
            FinancialData.company_code == stock_code,
            FinancialData.report_type == rt,
        )
        .order_by(FinancialData.report_date.desc(), AccountSubject.sort_order if AccountSubject.sort_order is not None else FinancialData.subject_code)
    )
    rows = (await session.execute(stmt)).all()

    # 4. 按 report_date 分组，限制 years 个年度
    periods_map: Dict[str, List[FinancialDataItem]] = {}
    period_labels: Dict[str, str] = {}
    seen_dates = set()
    for fd, subject_name in rows:
        rd = str(fd.report_date)
        if rd not in periods_map:
            if len(seen_dates) >= years:
                continue
            seen_dates.add(rd)
            periods_map[rd] = []
            rp = fd.report_period.value if fd.report_period else "annual"
            period_labels[rd] = rp
        if rd in periods_map:
            val = float(fd.value_decimal) if fd.value_decimal is not None else None
            periods_map[rd].append(
                FinancialDataItem(
                    subject_code=fd.subject_code or "",
                    subject_name=subject_name or fd.subject_code or "",
                    value=val,
                )
            )

    periods = [
        FinancialDataPeriod(
            report_date=rd,
            report_period=period_labels.get(rd, "annual"),
            items=items,
        )
        for rd, items in sorted(
            periods_map.items(), key=lambda x: x[0], reverse=True
        )
    ]

    return FinancialDataResponse(
        company_code=stock_code,
        company_name=company.stock_name or company.company_name or stock_code,
        report_type=report_type,
        periods=periods,
    )


def _company_to_response(c: Company) -> CompanyResponse:
    return CompanyResponse(
        stock_code=c.stock_code,
        stock_name=c.stock_name,
        company_name=c.company_name,
        exchange_id=c.exchange_id,
        exchange_name=c.exchange.name if hasattr(c, 'exchange') and c.exchange else None,
        industry_id=c.industry_id,
        industry_name=c.industry.name if hasattr(c, 'industry') and c.industry else None,
        listing_date=c.listing_date,
        current_price=float(c.current_price) if c.current_price else None,
        market_cap=float(c.market_cap) if c.market_cap else None,
        pe_ratio=float(c.pe_ratio) if c.pe_ratio else None,
        pb_ratio=float(c.pb_ratio) if c.pb_ratio else None,
        status=c.status.value,
        updated_at=c.updated_at.isoformat()
    )
