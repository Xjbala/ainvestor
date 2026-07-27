# -*- coding: utf-8 -*-
"""
爬虫任务 API 路由

提供爬虫任务管理接口。
"""

import logging
from datetime import date, datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_current_user, require_admin, get_current_user_optional
from ..persistence.db import get_db_session
from ..persistence.orm_models import User
from ..persistence.financial_models import (
    CrawlerTask, CrawlerTaskStatus, CrawlerDataType,
    DataSource, DataSourceType, Company, QualitativeReport, NewsSentiment
)
from ..crawler.sina_crawler import SinaCrawlerService
from ..crawler.crawler_engine import crawler_engine
from fastapi import BackgroundTasks

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crawler", tags=["数据采集"])

# 内置数据源定义：缺失时自动补齐，避免仅因 init_data 未跑导致 400
_BUILTIN_DATA_SOURCES: dict[str, dict] = {
    "sina": {
        "name": "新浪财经",
        "base_url": "https://finance.sina.com.cn",
        "api_type": DataSourceType.HTML,
    },
    "exchange_api": {
        "name": "交易所官方API",
        "base_url": "",
        "api_type": DataSourceType.JSON,
    },
    "cninfo": {
        "name": "巨潮资讯网",
        "base_url": "http://www.cninfo.com.cn",
        "api_type": DataSourceType.HTML,
    },
    "sina_news": {
        "name": "新浪财经新闻",
        "base_url": "https://finance.sina.com.cn",
        "api_type": DataSourceType.HTML,
    },
}


async def _get_or_create_data_source(
    session: AsyncSession,
    code: str,
) -> DataSource:
    """按 code 查找数据源；内置源缺失时自动创建。"""
    result = await session.execute(
        select(DataSource).where(DataSource.code == code)
    )
    data_source = result.scalar_one_or_none()
    if data_source:
        return data_source

    builtin = _BUILTIN_DATA_SOURCES.get(code)
    if not builtin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"数据源不存在: {code}",
        )

    data_source = DataSource(
        code=code,
        name=builtin["name"],
        base_url=builtin.get("base_url") or None,
        api_type=builtin["api_type"],
        is_active=True,
    )
    session.add(data_source)
    await session.flush()
    logger.info(f"Auto-created missing data source: {code}")
    return data_source


# ============================================================
# 请求/响应模型
# ============================================================

class CreateTaskRequest(BaseModel):
    """创建爬虫任务请求"""
    task_name: str = Field(..., description="任务名称")
    data_source_code: str = Field(default="sina", description="数据源代码")
    data_type: str = Field(..., description="数据类型: company_list, balance_sheet, income_statement, cash_flow, stock_price, batch_financial_data")
    target_companies: Optional[List[str]] = Field(None, description="目标公司列表(股票代码)。全量采集时留空表示全部公司")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    scheduled_time: Optional[datetime] = Field(None, description="计划执行时间")
    years: Optional[List[int]] = Field(None, description="采集年份列表，如 [2021,2022,2023,2024,2025]。全量采集时默认最近5年")


class TaskResponse(BaseModel):
    """任务响应"""
    id: str
    task_name: str
    data_source_id: int
    data_type: str
    status: str
    progress: float
    total_count: int
    success_count: int
    error_count: int
    # 任务明细日志（执行过程/错误样本），前端可展开查看
    detail_log: Optional[str] = None
    target_companies: Optional[List[str]] = None
    scheduled_time: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: List[TaskResponse]
    total: int
    skip: int
    limit: int


class DataSourceResponse(BaseModel):
    """数据源响应"""
    id: int
    code: str
    name: str
    api_type: str
    is_active: bool
    rate_limit: int
    timeout: int


class CompanyListResponse(BaseModel):
    """公司列表响应"""
    companies: List[dict]
    total: int


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str


# ============================================================
# 数据源路由
# ============================================================

@router.get("/sources", response_model=List[DataSourceResponse])
async def list_data_sources(
    session: AsyncSession = Depends(get_db_session),
):
    """
    获取可用数据源列表
    """
    result = await session.execute(
        select(DataSource).where(DataSource.is_active == True)
    )
    sources = result.scalars().all()

    return [
        DataSourceResponse(
            id=s.id,
            code=s.code,
            name=s.name,
            api_type=s.api_type.value,
            is_active=s.is_active,
            rate_limit=s.rate_limit,
            timeout=s.timeout,
        )
        for s in sources
    ]


# ============================================================
# 任务管理路由
# ============================================================

@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    request: CreateTaskRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    创建爬虫任务
    """
    data_source = await _get_or_create_data_source(session, request.data_source_code)

    # 解析数据类型
    try:
        data_type = CrawlerDataType(request.data_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的数据类型: {request.data_type}",
        )

    # 创建任务
    task = CrawlerTask(
        id=str(uuid4()),
        task_name=request.task_name,
        data_source_id=data_source.id,
        data_type=data_type,
        target_companies=request.target_companies,
        start_date=request.start_date,
        end_date=request.end_date,
        scheduled_time=request.scheduled_time,
        created_by=current_user.id if current_user else None,
    )

    session.add(task)
    await session.commit()
    await session.refresh(task)

    username = current_user.username if current_user else "anonymous"
    logger.info(f"Created crawler task: {task.task_name} by {username}")

    # 触发后台执行
    background_tasks.add_task(crawler_engine.execute_task, task.id)

    return _task_to_response(task)


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, description="状态筛选"),
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    获取任务列表
    """
    query = select(CrawlerTask).order_by(CrawlerTask.created_at.desc())

    if status_filter:
        try:
            status_enum = CrawlerTaskStatus(status_filter)
            query = query.where(CrawlerTask.status == status_enum)
        except ValueError:
            pass

    query = query.offset(skip).limit(limit)

    result = await session.execute(query)
    tasks = result.scalars().all()

    return TaskListResponse(
        tasks=[_task_to_response(t) for t in tasks],
        total=len(tasks),
        skip=skip,
        limit=limit,
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    获取任务详情
    """
    result = await session.execute(
        select(CrawlerTask).where(CrawlerTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在",
        )

    return _task_to_response(task)


@router.post("/tasks/{task_id}/cancel", response_model=MessageResponse)
async def cancel_task(
    task_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    取消任务
    """
    result = await session.execute(
        select(CrawlerTask).where(CrawlerTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在",
        )

    if task.status not in (CrawlerTaskStatus.PENDING, CrawlerTaskStatus.RUNNING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能取消待执行或执行中的任务",
        )

    task.status = CrawlerTaskStatus.CANCELLED
    task.completed_at = datetime.utcnow()
    await session.commit()

    logger.info(f"Cancelled task {task.task_name} by {current_user.username if current_user else 'anonymous'}")

    return MessageResponse(message="任务已取消")


@router.delete("/tasks/{task_id}", response_model=MessageResponse)
async def delete_task(
    task_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    删除任务
    """
    result = await session.execute(
        select(CrawlerTask).where(CrawlerTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在",
        )

    if task.status == CrawlerTaskStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法删除执行中的任务",
        )

    await session.delete(task)
    await session.commit()

    logger.info(f"Deleted task {task.task_name} by {current_user.username if current_user else 'anonymous'}")

    return MessageResponse(message="任务已删除")


# ============================================================
# 全量批量采集路由
# ============================================================

class BatchFinancialRequest(BaseModel):
    """批量财务数据采集请求"""
    task_name: str = Field(default="全量财务数据批量采集", description="任务名称")
    data_source_code: str = Field(default="sina", description="数据源代码")
    years: Optional[List[int]] = Field(None, description="采集年份列表，如 [2021,2022,2023,2024,2025]。默认最近5年")


class QualitativeCollectionRequest(BaseModel):
    """定性数据采集请求"""
    task_name: str = Field(default="定性数据采集", description="任务名称")
    data_source_code: str = Field(default="cninfo", description="数据源代码")
    target_companies: List[str] = Field(..., description="目标公司列表(股票代码)")
    report_types: Optional[List[str]] = Field(default=["annual", "semi", "q1", "q3"], description="报告类型: annual/semi/q1/q3")
    years: Optional[List[int]] = Field(None, description="采集年份列表")


class NewsCollectionRequest(BaseModel):
    """新闻舆情采集请求"""
    task_name: str = Field(default="新闻舆情采集", description="任务名称")
    data_source_code: str = Field(default="sina_news", description="数据源代码")
    target_companies: List[str] = Field(..., description="目标公司列表(股票代码)")


@router.post("/tasks/batch-financial", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_batch_financial_task(
    request: BatchFinancialRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    创建全量财务数据批量采集任务

    自动获取所有活跃上市公司，并发采集三大报表（资产负债表、利润表、现金流量表）。
    支持断点续采：已存在数据的公司将自动跳过。

    Args:
        task_name: 任务名称
        data_source_code: 数据源代码（默认 sina）
        years: 采集年份列表，如 [2021,2022,2023,2024,2025]，默认最近5年
    """
    data_source = await _get_or_create_data_source(session, request.data_source_code)

    # 创建任务
    task = CrawlerTask(
        id=str(uuid4()),
        task_name=request.task_name,
        data_source_id=data_source.id,
        data_type=CrawlerDataType.BATCH_FINANCIAL_DATA,
        extra_params={"years": [str(y) for y in (request.years or [])]},
        created_by=current_user.id if current_user else None,
    )

    session.add(task)
    await session.commit()
    await session.refresh(task)

    username = current_user.username if current_user else "anonymous"
    logger.info(f"Created batch financial task: {task.task_name} by {username}, years={request.years}")

    # 触发后台执行
    background_tasks.add_task(crawler_engine.execute_task, task.id)

    return _task_to_response(task)


@router.post("/tasks/qualitative", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_qualitative_task(
    request: QualitativeCollectionRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    创建定性数据采集任务

    从巨潮资讯网下载年报/季报PDF，解析为Markdown，提取结构化MD&A数据。

    Args:
        task_name: 任务名称
        data_source_code: 数据源代码（默认 cninfo）
        target_companies: 目标公司列表(股票代码)
        report_types: 报告类型列表 (annual/semi/q1/q3)
        years: 采集年份列表
    """
    data_source = await _get_or_create_data_source(session, request.data_source_code)

    # 创建任务
    task = CrawlerTask(
        id=str(uuid4()),
        task_name=request.task_name,
        data_source_id=data_source.id,
        data_type=CrawlerDataType.QUALITATIVE_REPORT,
        target_companies=request.target_companies,
        extra_params={
            "report_types": request.report_types,
            "years": [str(y) for y in (request.years or [])],
        },
        created_by=current_user.id if current_user else None,
    )

    session.add(task)
    await session.commit()
    await session.refresh(task)

    username = current_user.username if current_user else "anonymous"
    logger.info(f"Created qualitative task: {task.task_name} by {username}, companies={request.target_companies}")

    # 触发后台执行
    background_tasks.add_task(crawler_engine.execute_task, task.id)

    return _task_to_response(task)


@router.post("/tasks/news", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_news_task(
    request: NewsCollectionRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    创建新闻舆情采集任务

    从新浪财经等平台采集上市公司相关新闻，并进行简单情绪分析。

    Args:
        task_name: 任务名称
        data_source_code: 数据源代码（默认 sina_news）
        target_companies: 目标公司列表(股票代码)
    """
    data_source = await _get_or_create_data_source(session, request.data_source_code)

    # 创建任务
    task = CrawlerTask(
        id=str(uuid4()),
        task_name=request.task_name,
        data_source_id=data_source.id,
        data_type=CrawlerDataType.NEWS_SENTIMENT,
        target_companies=request.target_companies,
        created_by=current_user.id if current_user else None,
    )

    session.add(task)
    await session.commit()
    await session.refresh(task)

    username = current_user.username if current_user else "anonymous"
    logger.info(f"Created news task: {task.task_name} by {username}, companies={request.target_companies}")

    # 触发后台执行
    background_tasks.add_task(crawler_engine.execute_task, task.id)

    return _task_to_response(task)


# ============================================================
# 定性数据查询路由
# ============================================================

class QualitativeReportResponse(BaseModel):
    """定性报告响应"""
    id: int
    company_code: str
    report_type: str
    report_period: str
    publish_date: str
    overview: Optional[str] = None
    revenue_analysis: Optional[str] = None
    cost_analysis: Optional[str] = None
    rd_investment: Optional[str] = None
    core_competencies: Optional[str] = None
    risk_factors: Optional[str] = None
    risk_keywords: Optional[list] = None
    future_outlook: Optional[str] = None
    capacity_plans: Optional[str] = None
    management_discussion: Optional[str] = None
    raw_markdown_length: Optional[int] = None
    extraction_method: Optional[str] = None
    source_url: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/qualitative/{stock_code}", response_model=List[QualitativeReportResponse])
async def get_qualitative_reports(
    stock_code: str,
    include_markdown: bool = Query(False, description="是否包含完整Markdown全文"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    获取公司定性报告列表
    """
    stmt = (
        select(QualitativeReport)
        .where(QualitativeReport.company_code == stock_code)
        .order_by(QualitativeReport.report_period.desc())
    )
    result = await session.execute(stmt)
    reports = result.scalars().all()

    return [
        _qualitative_report_to_response(r, include_markdown)
        for r in reports
    ]


@router.get("/qualitative/{stock_code}/latest", response_model=Optional[QualitativeReportResponse])
async def get_latest_qualitative_report(
    stock_code: str,
    include_markdown: bool = Query(False, description="是否包含完整Markdown全文"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    获取公司最新的定性报告
    """
    stmt = (
        select(QualitativeReport)
        .where(QualitativeReport.company_code == stock_code)
        .order_by(QualitativeReport.report_period.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        return None

    return _qualitative_report_to_response(report, include_markdown)


# ============================================================
# 新闻情绪查询路由
# ============================================================

class NewsSentimentResponse(BaseModel):
    """新闻舆情响应"""
    id: int
    title: str
    url: Optional[str]
    publish_date: str
    sentiment_score: float
    sentiment_label: str
    keywords: Optional[list]

    class Config:
        from_attributes = True


@router.get("/news/{stock_code}", response_model=List[NewsSentimentResponse])
async def get_news_sentiment(
    stock_code: str,
    days: int = Query(90, ge=1, le=365, description="最近N天的新闻"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    获取公司新闻情绪数据
    """
    from datetime import timedelta

    cutoff_date = date.today() - timedelta(days=days)
    stmt = (
        select(NewsSentiment)
        .where(
            NewsSentiment.company_code == stock_code,
            NewsSentiment.publish_date >= cutoff_date,
        )
        .order_by(NewsSentiment.publish_date.desc())
    )
    result = await session.execute(stmt)
    news_items = result.scalars().all()

    return [
        NewsSentimentResponse(
            id=n.id,
            title=n.title,
            url=n.url,
            publish_date=str(n.publish_date),
            sentiment_score=n.sentiment_score,
            sentiment_label=n.sentiment_label,
            keywords=n.keywords,
        )
        for n in news_items
    ]


# ============================================================
# 辅助函数
# ============================================================

def _qualitative_report_to_response(
    r: QualitativeReport,
    include_markdown: bool = False,
) -> QualitativeReportResponse:
    """转换定性报告为响应模型"""
    return QualitativeReportResponse(
        id=r.id,
        company_code=r.company_code,
        report_type=r.report_type,
        report_period=str(r.report_period),
        publish_date=str(r.publish_date) if r.publish_date else None,
        overview=r.overview,
        revenue_analysis=r.revenue_analysis,
        cost_analysis=r.cost_analysis,
        rd_investment=r.rd_investment,
        core_competencies=r.core_competencies,
        risk_factors=r.risk_factors,
        risk_keywords=r.risk_keywords,
        future_outlook=r.future_outlook,
        capacity_plans=r.capacity_plans,
        management_discussion=r.management_discussion if include_markdown else None,
        raw_markdown_length=r.raw_markdown_length,
        extraction_method=r.extraction_method,
        source_url=r.source_url,
    )


def _task_to_response(task: CrawlerTask) -> TaskResponse:
    """转换任务为响应模型"""
    return TaskResponse(
        id=task.id,
        task_name=task.task_name,
        data_source_id=task.data_source_id,
        data_type=task.data_type.value,
        status=task.status.value,
        progress=float(task.progress or 0),
        total_count=task.total_count or 0,
        success_count=task.success_count or 0,
        error_count=task.error_count or 0,
        detail_log=task.error_log,
        target_companies=task.target_companies,
        scheduled_time=task.scheduled_time.isoformat() if task.scheduled_time else None,
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        created_at=task.created_at.isoformat() if task.created_at else datetime.utcnow().isoformat(),
    )
