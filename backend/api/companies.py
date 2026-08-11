# -*- coding: utf-8 -*-
"""
公司管理 API 路由

提供上市公司基本信息的查询、统计和管理接口。
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer, joinedload
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
from ..analysis.financial_validation import (
    CORE_SUBJECTS,
    core_subjects_for_profile,
    validate_period,
    validation_profile_for_industry,
    summarize_periods,
)
from ..analysis.coverage_service import (
    default_coverage_years,
    normalize_report_types,
    build_scope_key,
    extract_gap_items,
    scan_coverage,
    scan_and_save,
    get_latest_snapshot,
    get_snapshot_gap_items,
    list_snapshots,
    paginate_snapshot_companies,
    snapshot_has_company_details,
    snapshot_to_dict,
    paginate_coverage_result,
    core_subjects_payload,
)

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


def _parse_years_param(years: Optional[str]) -> List[int]:
    if not years:
        return default_coverage_years()
    return default_coverage_years(
        [int(y.strip()) for y in years.split(",") if y.strip().isdigit()]
    )


@router.get("/financial-coverage")
async def get_financial_coverage(
    years: Optional[str] = Query(
        None,
        description="逗号分隔年份，如 2021,2022,2023；默认最近5个完整财年",
    ),
    report_types: str = Query("BS,IS,CF", description="报表类型，逗号分隔"),
    status_filter: str = Query("active", description="公司状态: active/all"),
    search: Optional[str] = Query(None, description="按代码/名称过滤公司宇宙"),
    stock_codes: Optional[str] = Query(None, description="逗号分隔股票代码，限定扫描范围"),
    only_gaps: bool = Query(False, description="仅返回有缺口的公司"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    include_cells: bool = Query(True, description="是否返回每公司矩阵明细"),
    use_snapshot: bool = Query(
        True,
        description="优先读取最新快照；无快照或指定股票范围时回退在线扫描",
    ),
    refresh: bool = Query(False, description="强制在线重扫（全市场时会落库新快照）"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    财务数据覆盖率看板。

    默认读最新快照；可 refresh=true 强制重扫并落库。
    指定 stock_codes 时在线计算；名称/代码搜索可复用全市场快照。
    """
    year_list = _parse_years_param(years)
    rt_list = normalize_report_types(
        [rt.strip() for rt in report_types.split(",") if rt.strip()]
    )
    codes = [c.strip() for c in (stock_codes or "").split(",") if c.strip()] or None
    has_search = bool(search and search.strip())

    raw: Dict[str, Any]
    if refresh and not codes and not has_search:
        raw = await scan_and_save(
            session,
            years=year_list,
            report_types=rt_list,
            status_filter=status_filter,
            source="api_refresh",
        )
    elif use_snapshot and not codes and not refresh:
        snap = await get_latest_snapshot(
            session,
            years=year_list,
            report_types=rt_list,
            status_filter=status_filter,
            include_payload=False,
        )
        if snap and await snapshot_has_company_details(session, snap):
            return await paginate_snapshot_companies(
                session,
                snap,
                only_gaps=only_gaps,
                page=page,
                page_size=page_size,
                include_cells=include_cells,
                search=search,
            )
        if snap:
            await session.refresh(snap, attribute_names=["companies_payload"])
            raw = snapshot_to_dict(snap, include_companies=True)
            raw["status_filter"] = status_filter
        else:
            raw = await scan_coverage(
                session,
                years=year_list,
                report_types=rt_list,
                status_filter=status_filter,
                search=search if has_search else None,
            )
    else:
        raw = await scan_coverage(
            session,
            years=year_list,
            report_types=rt_list,
            status_filter=status_filter,
            stock_codes=codes,
            search=search if has_search else None,
        )

    return paginate_coverage_result(
        raw,
        only_gaps=only_gaps,
        page=page,
        page_size=page_size,
        include_cells=include_cells,
        search=search,
    )


@router.post("/financial-coverage/scan")
async def scan_financial_coverage(
    years: Optional[str] = Query(None, description="逗号分隔年份"),
    report_types: str = Query("BS,IS,CF"),
    status_filter: str = Query("active"),
    persist: bool = Query(True, description="是否落库快照"),
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    手动触发全市场覆盖率扫描。

    默认落库快照，供后续看板秒开。
    """
    year_list = _parse_years_param(years)
    rt_list = normalize_report_types(
        [rt.strip() for rt in report_types.split(",") if rt.strip()]
    )
    created_by = current_user.id if current_user else None
    if persist:
        raw = await scan_and_save(
            session,
            years=year_list,
            report_types=rt_list,
            status_filter=status_filter,
            source="manual_scan",
            created_by=created_by,
        )
    else:
        raw = await scan_coverage(
            session,
            years=year_list,
            report_types=rt_list,
            status_filter=status_filter,
        )
    return paginate_coverage_result(
        raw,
        only_gaps=False,
        page=1,
        page_size=20,
        include_cells=False,
    )


@router.get("/financial-coverage/snapshots")
async def list_financial_coverage_snapshots(
    years: Optional[str] = Query(None),
    report_types: str = Query("BS,IS,CF"),
    status_filter: str = Query("active"),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    """列出覆盖率快照历史（不含公司明细）。"""
    year_list = _parse_years_param(years)
    rt_list = normalize_report_types(
        [rt.strip() for rt in report_types.split(",") if rt.strip()]
    )
    scope = build_scope_key(year_list, rt_list, status_filter)
    snaps = await list_snapshots(session, scope_key=scope, limit=limit)
    return {
        "scope_key": scope,
        "items": [
            {
                "snapshot_id": s.id,
                "scope_key": s.scope_key,
                "years": s.years,
                "report_types": s.report_types,
                "status_filter": s.status_filter,
                "source": s.source,
                "trigger_task_id": s.trigger_task_id,
                "company_count": s.company_count,
                "gap_company_count": s.gap_company_count,
                "coverage_rate": float(s.coverage_rate or 0),
                "complete_cells": s.complete_cells,
                "partial_cells": s.partial_cells,
                "missing_cells": s.missing_cells,
                "matrix_total": s.matrix_total,
                "scan_duration_ms": s.scan_duration_ms,
                "scanned_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in snaps
        ],
    }


@router.get("/financial-coverage/snapshots/{snapshot_id}")
async def get_financial_coverage_snapshot(
    snapshot_id: int,
    only_gaps: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    include_cells: bool = Query(True),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session),
):
    """读取指定快照详情。"""
    from ..persistence.financial_models import FinancialCoverageSnapshot

    stmt = (
        select(FinancialCoverageSnapshot)
        .where(FinancialCoverageSnapshot.id == snapshot_id)
        .options(defer(FinancialCoverageSnapshot.companies_payload))
    )
    snap = (await session.execute(stmt)).scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=404, detail="快照不存在")
    if await snapshot_has_company_details(session, snap):
        return await paginate_snapshot_companies(
            session,
            snap,
            only_gaps=only_gaps,
            page=page,
            page_size=page_size,
            include_cells=include_cells,
            search=search,
        )
    await session.refresh(snap, attribute_names=["companies_payload"])
    raw = snapshot_to_dict(snap, include_companies=True)
    return paginate_coverage_result(
        raw,
        only_gaps=only_gaps,
        page=page,
        page_size=page_size,
        include_cells=include_cells,
        search=search,
    )


@router.get("/financial-gaps")
async def get_financial_gaps(
    years: Optional[str] = Query(None, description="逗号分隔年份"),
    report_types: str = Query("BS,IS,CF"),
    status_filter: str = Query("active"),
    search: Optional[str] = Query(None),
    stock_codes: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000, description="最多返回多少个缺口单元"),
    use_snapshot: bool = Query(True, description="优先使用快照"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    返回可直接用于补采的缺口清单。

    每个 gap: company + report_type + year + missing_required
    """
    year_list = _parse_years_param(years)
    rt_list = normalize_report_types(
        [rt.strip() for rt in report_types.split(",") if rt.strip()]
    )
    codes = [c.strip() for c in (stock_codes or "").split(",") if c.strip()] or None
    has_search = bool(search and search.strip())
    snap = None
    if use_snapshot and not codes:
        snap = await get_latest_snapshot(
            session,
            years=year_list,
            report_types=rt_list,
            status_filter=status_filter,
            include_payload=False,
        )

    if snap and await snapshot_has_company_details(session, snap):
        gaps = await get_snapshot_gap_items(
            session,
            snap,
            limit=limit,
            search=search,
        )
        coverage_meta = {
            "years": snap.years or [],
            "report_types": snap.report_types or [],
            "summary": snap.summary or {},
            "from_snapshot": True,
            "snapshot_id": snap.id,
            "scanned_at": snap.created_at.isoformat() if snap.created_at else None,
        }
    else:
        raw = await scan_coverage(
            session,
            years=year_list,
            report_types=rt_list,
            status_filter=status_filter,
            stock_codes=codes,
            search=search if has_search else None,
        )
        gaps = extract_gap_items(raw.get("companies") or [], limit=limit)
        coverage_meta = {
            "years": raw["years"],
            "report_types": raw["report_types"],
            "summary": raw["summary"],
            "from_snapshot": False,
            "snapshot_id": None,
            "scanned_at": None,
        }

    repair_targets: Dict[str, Dict[str, Any]] = {}
    for g in gaps:
        code = g["stock_code"]
        item = repair_targets.setdefault(
            code,
            {
                "stock_code": code,
                "stock_name": g["stock_name"],
                "years": set(),
                "report_types": set(),
                "gap_count": 0,
            },
        )
        item["years"].add(g["year"])
        item["report_types"].add(g["report_type"])
        item["gap_count"] += 1

    targets = []
    for item in repair_targets.values():
        targets.append(
            {
                "stock_code": item["stock_code"],
                "stock_name": item["stock_name"],
                "years": sorted(item["years"]),
                "report_types": sorted(item["report_types"]),
                "gap_count": item["gap_count"],
            }
        )
    targets.sort(key=lambda x: (-x["gap_count"], x["stock_code"]))

    return {
        "years": coverage_meta["years"],
        "report_types": coverage_meta["report_types"],
        "summary": coverage_meta["summary"],
        "gap_count": len(gaps),
        "gaps": gaps,
        "repair_targets": targets,
        "from_snapshot": coverage_meta.get("from_snapshot"),
        "snapshot_id": coverage_meta.get("snapshot_id"),
        "scanned_at": coverage_meta.get("scanned_at"),
    }


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

class SubjectCheckItem(BaseModel):
    code: str
    name: str
    required: bool
    present: bool
    value: Optional[float] = None

class AccountingCheckItem(BaseModel):
    key: str
    name: str
    passed: bool
    left_label: str
    left_value: Optional[float] = None
    right_label: str
    right_value: Optional[float] = None
    diff: Optional[float] = None
    message: str = ""
    severity: str = "error"

class PeriodValidationItem(BaseModel):
    report_type: str
    report_date: str
    status: str
    subject_count: int = 0
    core_total: int = 0
    core_present: int = 0
    core_required_total: int = 0
    core_required_present: int = 0
    core_hit_rate: float = 0.0
    missing_required: List[Dict[str, str]] = []
    missing_optional: List[Dict[str, str]] = []
    core_subjects: List[SubjectCheckItem] = []
    accounting_checks: List[AccountingCheckItem] = []
    summary: str = ""

class ValidationSummary(BaseModel):
    overall_status: str
    period_count: int = 0
    pass_count: int = 0
    partial_count: int = 0
    fail_count: int = 0
    empty_count: int = 0
    avg_core_hit_rate: float = 0.0
    summary: str = ""

class FinancialDataPeriod(BaseModel):
    """单个报告期的全部科目"""
    report_date: str
    report_period: str
    items: List[FinancialDataItem]
    validation: Optional[PeriodValidationItem] = None

class FinancialDataResponse(BaseModel):
    """财务数据响应"""
    company_code: str
    company_name: str
    report_type: str
    periods: List[FinancialDataPeriod]
    validation_summary: Optional[ValidationSummary] = None
    core_subjects: Optional[List[Dict[str, Any]]] = None


@router.get("/{stock_code}/financial-data", response_model=FinancialDataResponse)
async def get_financial_data(
    stock_code: str,
    report_type: str = Query("BS", description="报表类型: BS/IS/CF"),
    years: int = Query(5, ge=1, le=20, description="查询年数"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    获取公司原始财务数据（资产负债表/利润表/现金流量表）

    返回多年对比数据，按报告期分组，每个科目包含代码、名称和数值，
    并附带核心科目完整性与会计勾稽校验结果。
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
    industry_code = None
    industry_name = None
    if company.industry_id:
        industry_code, industry_name = (
            await session.execute(
                select(Industry.code, Industry.name).where(Industry.id == company.industry_id)
            )
        ).one_or_none() or (None, None)
    validation_profile = validation_profile_for_industry(
        industry_code, industry_name, company.stock_name or company.company_name
    )
    # 优先年报：每年只保留一个报告期（12-31 优先，否则取该年最新一期）
    stmt = (
        select(FinancialData, AccountSubject.name)
        .outerjoin(AccountSubject, FinancialData.subject_id == AccountSubject.id)
        .where(
            FinancialData.company_code == stock_code,
            FinancialData.report_type == rt,
        )
        .order_by(
            FinancialData.report_date.desc(),
            # MySQL 不支持 NULLS LAST；用 ISNULL 把空 sort_order 排后
            func.isnull(AccountSubject.sort_order).asc(),
            AccountSubject.sort_order.asc(),
            FinancialData.subject_code.asc(),
        )
    )
    rows = (await session.execute(stmt)).all()

    # 4. 先按 report_date 聚合，再按年份择优，限制 years 个年度
    raw_periods: Dict[str, List[FinancialDataItem]] = {}
    period_labels: Dict[str, str] = {}
    for fd, subject_name in rows:
        if not fd.report_date:
            continue
        rd = str(fd.report_date)
        if rd not in raw_periods:
            raw_periods[rd] = []
            if fd.report_period:
                period_labels[rd] = fd.report_period.value
            elif fd.report_date.month == 12:
                period_labels[rd] = "annual"
            elif fd.report_date.month == 6:
                period_labels[rd] = "semi_annual"
            elif fd.report_date.month == 3:
                period_labels[rd] = "q1"
            elif fd.report_date.month == 9:
                period_labels[rd] = "q3"
            else:
                period_labels[rd] = "annual"
        val = float(fd.value_decimal) if fd.value_decimal is not None else None
        raw_periods[rd].append(
            FinancialDataItem(
                subject_code=fd.subject_code or "",
                subject_name=subject_name or fd.subject_code or "",
                value=val,
            )
        )

    # year -> 选中的 report_date
    selected_by_year: Dict[int, str] = {}
    for rd in sorted(raw_periods.keys(), reverse=True):
        try:
            y = int(rd[:4])
            month = int(rd[5:7])
        except (TypeError, ValueError):
            continue
        prev = selected_by_year.get(y)
        if prev is None:
            selected_by_year[y] = rd
            continue
        # 已有候选时：12 月年报优先；同为非年报则保留更新的一期（已按 desc 遍历）
        try:
            prev_month = int(prev[5:7])
        except (TypeError, ValueError):
            prev_month = 0
        if month == 12 and prev_month != 12:
            selected_by_year[y] = rd

    chosen_years = sorted(selected_by_year.keys(), reverse=True)[:years]
    periods_map: Dict[str, List[FinancialDataItem]] = {
        selected_by_year[y]: raw_periods[selected_by_year[y]]
        for y in chosen_years
        if selected_by_year[y] in raw_periods
    }

    period_validations = []
    periods: List[FinancialDataPeriod] = []
    for rd, items in sorted(periods_map.items(), key=lambda x: x[0], reverse=True):
        validation = validate_period(
            report_type,
            rd,
            [item.model_dump() for item in items],
            profile=validation_profile,
        )
        period_validations.append(validation)
        periods.append(
            FinancialDataPeriod(
                report_date=rd,
                report_period=period_labels.get(rd, "annual"),
                items=items,
                validation=PeriodValidationItem(**validation.to_dict()),
            )
        )

    summary = summarize_periods(period_validations)
    core_defs = [
        {"code": s["code"], "name": s["name"], "required": bool(s.get("required"))}
        for s in core_subjects_for_profile(report_type, validation_profile)
    ]

    return FinancialDataResponse(
        company_code=stock_code,
        company_name=company.stock_name or company.company_name or stock_code,
        report_type=report_type,
        periods=periods,
        validation_summary=ValidationSummary(**summary),
        core_subjects=core_defs,
    )


@router.get("/{stock_code}/financial-validation")
async def get_financial_validation(
    stock_code: str,
    report_type: str = Query("BS", description="报表类型: BS/IS/CF"),
    years: int = Query(5, ge=1, le=20, description="查询年数"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    仅返回财务数据完整性 / 勾稽校验结果（不返回全部科目明细）。
    """
    data = await get_financial_data(
        stock_code=stock_code,
        report_type=report_type,
        years=years,
        session=session,
    )
    return {
        "company_code": data.company_code,
        "company_name": data.company_name,
        "report_type": data.report_type,
        "validation_summary": data.validation_summary,
        "core_subjects": data.core_subjects,
        "periods": [
            {
                "report_date": p.report_date,
                "report_period": p.report_period,
                "validation": p.validation,
            }
            for p in data.periods
        ],
    }


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
