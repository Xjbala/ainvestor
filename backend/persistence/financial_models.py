# -*- coding: utf-8 -*-
"""
财务数据模型

包含公司、行业、交易所、科目编码、财务数据等核心模型。
移植自 leofun 项目，使用 SQLAlchemy ORM。
"""

import enum
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, BigInteger, Text, Boolean, Date, DateTime,
    ForeignKey, Index, Numeric, Enum, JSON, UniqueConstraint, Float
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .db import Base

# MySQL TEXT 约 64KB；年报 Markdown 常超限。用 MEDIUMTEXT（~16MB）。
# 非 MySQL 方言回退为普通 Text。
LongText = Text().with_variant(MEDIUMTEXT(), "mysql")


# ============================================================
# 枚举类型定义
# ============================================================

class CompanyStatus(str, enum.Enum):
    """公司状态"""
    ACTIVE = "active"       # 正常
    SUSPENDED = "suspended" # 停牌
    DELISTED = "delisted"   # 退市
    ST = "st"               # ST股票


class ReportType(str, enum.Enum):
    """报表类型"""
    BS = "BS"  # 资产负债表
    IS = "IS"  # 利润表
    CF = "CF"  # 现金流量表
    OE = "OE"  # 所有者权益变动表


class ReportPeriod(str, enum.Enum):
    """报告期间"""
    ANNUAL = "annual"           # 年报
    SEMI_ANNUAL = "semi_annual" # 中报
    Q1 = "q1"                   # 一季度
    Q3 = "q3"                   # 三季度


class DataType(str, enum.Enum):
    """数据类型"""
    DECIMAL = "decimal"
    TEXT = "text"
    DATE = "date"
    BOOLEAN = "boolean"


class SubjectCategory(str, enum.Enum):
    """科目类别"""
    # 资产负债表
    A = "A"   # 资产
    L = "L"   # 负债
    E = "E"   # 所有者权益
    # 利润表
    I = "I"   # 收入
    C = "C"   # 成本
    F = "F"   # 费用
    # 现金流量表
    O = "O"   # 经营活动
    IV = "IV" # 投资活动
    FN = "FN" # 筹资活动
    # 所有者权益变动表
    OC = "OC" # 权益变动


class CrawlerTaskStatus(str, enum.Enum):
    """爬虫任务状态"""
    PENDING = "pending"     # 待执行
    RUNNING = "running"     # 执行中
    SUCCESS = "success"     # 成功
    FAILED = "failed"       # 失败
    CANCELLED = "cancelled" # 已取消


class DataSourceType(str, enum.Enum):
    """数据源类型"""
    REST = "rest"   # REST API
    HTML = "html"   # HTML解析
    JSON = "json"   # JSON接口


class CrawlerDataType(str, enum.Enum):
    """爬虫数据类型"""
    COMPANY_LIST = "company_list"         # 公司列表
    BALANCE_SHEET = "balance_sheet"       # 资产负债表
    INCOME_STATEMENT = "income_statement" # 利润表
    CASH_FLOW = "cash_flow"               # 现金流量表
    STOCK_PRICE = "stock_price"           # 股价数据
    BATCH_FINANCIAL_DATA = "batch_financial_data"  # 全量财务数据批量采集
    QUALITATIVE_REPORT = "qualitative_report"    # 年报/季报PDF采集与MD&A提取
    NEWS_SENTIMENT = "news_sentiment"            # 新闻舆情采集


# ============================================================
# 基础数据模型
# ============================================================

class Exchange(Base):
    """交易所模型"""
    __tablename__ = "exchanges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True, comment="交易所代码")
    name: Mapped[str] = mapped_column(String(50), comment="交易所名称")
    country: Mapped[str] = mapped_column(String(50), default="中国", comment="所在国家")
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Shanghai", comment="时区")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否激活")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关系
    companies: Mapped[List["Company"]] = relationship("Company", back_populates="exchange")

    def __repr__(self) -> str:
        return f"<Exchange {self.code} - {self.name}>"


class Industry(Base):
    """行业分类模型"""
    __tablename__ = "industries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, comment="行业代码")
    name: Mapped[str] = mapped_column(String(100), comment="行业名称")
    level: Mapped[int] = mapped_column(Integer, default=1, comment="分类级别")
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("industries.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="行业描述")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否激活")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关系
    parent: Mapped[Optional["Industry"]] = relationship("Industry", remote_side="Industry.id", back_populates="children")
    children: Mapped[List["Industry"]] = relationship("Industry", back_populates="parent")
    companies: Mapped[List["Company"]] = relationship("Company", back_populates="industry")

    def __repr__(self) -> str:
        return f"<Industry {self.code} - {self.name}>"


class Company(Base):
    """公司基本信息模型"""
    __tablename__ = "companies"

    stock_code: Mapped[str] = mapped_column(String(10), primary_key=True, comment="股票代码")
    stock_name: Mapped[str] = mapped_column(String(100), comment="股票名称")
    company_name: Mapped[str] = mapped_column(String(200), comment="公司全称")
    exchange_id: Mapped[int] = mapped_column(Integer, ForeignKey("exchanges.id"), comment="交易所")
    industry_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("industries.id"), nullable=True)

    # 基本信息
    listing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="上市日期")
    registered_capital: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), nullable=True, comment="注册资本(万元)")
    total_shares: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="总股本(股)")
    circulating_shares: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="流通股本(股)")

    # 市场数据
    current_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True, comment="当前股价")
    market_cap: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), nullable=True, comment="总市值(万元)")
    pe_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True, default=0, comment="市盈率")
    pb_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True, default=0, comment="市净率")

    # 状态信息
    status: Mapped[CompanyStatus] = mapped_column(
        Enum(CompanyStatus), default=CompanyStatus.ACTIVE, comment="状态"
    )
    is_st: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否ST股")

    # 公司信息
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="公司官网")
    business_scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="经营范围")

    # 时间字段
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关系
    exchange: Mapped["Exchange"] = relationship("Exchange", back_populates="companies")
    industry: Mapped[Optional["Industry"]] = relationship("Industry", back_populates="companies")
    financial_data: Mapped[List["FinancialData"]] = relationship("FinancialData", back_populates="company")
    financial_match_issues: Mapped[List["FinancialMatchIssue"]] = relationship(
        "FinancialMatchIssue", back_populates="company"
    )

    __table_args__ = (
        Index("ix_companies_status", "status"),
        Index("ix_companies_listing_date", "listing_date"),
    )

    def __repr__(self) -> str:
        return f"<Company {self.stock_code} - {self.stock_name}>"

    @property
    def display_name(self) -> str:
        return f"{self.stock_code} {self.stock_name}"


# ============================================================
# 科目编码模型
# ============================================================

class AccountCategory(Base):
    """科目分类模型"""
    __tablename__ = "account_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, comment="分类代码")
    name: Mapped[str] = mapped_column(String(100), comment="分类名称")
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType), comment="报表类型")
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("account_categories.id"), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=1, comment="分类级别")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否激活")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关系
    parent: Mapped[Optional["AccountCategory"]] = relationship("AccountCategory", remote_side="AccountCategory.id")
    subjects: Mapped[List["AccountSubject"]] = relationship("AccountSubject", back_populates="category")

    def __repr__(self) -> str:
        return f"<AccountCategory {self.code} - {self.name}>"


class AccountSubject(Base):
    """科目编码模型 - 支持分层编码结构"""
    __tablename__ = "account_subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, comment="科目代码")
    name: Mapped[str] = mapped_column(String(100), comment="科目名称")
    sina_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="新浪财经名称")

    # 分类信息
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("account_categories.id"))
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType), default=ReportType.BS, comment="报表类型")
    subject_category: Mapped[str] = mapped_column(String(2), default="A", comment="科目类别")

    # 数据属性
    data_type: Mapped[DataType] = mapped_column(Enum(DataType), default=DataType.DECIMAL, comment="数据类型")
    unit: Mapped[str] = mapped_column(String(10), default="万元", comment="单位")
    currency: Mapped[str] = mapped_column(String(3), default="CNY", comment="币种")

    # 科目描述
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="科目说明")
    formula: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="计算公式")

    # 科目属性
    is_calculated: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否计算字段")
    is_summary: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否汇总科目")
    # 旧生产表仍为 NOT NULL 且无默认值；仅确保新增标准科目可写入，不参与任何业务逻辑。
    legacy_is_financial: Mapped[bool] = mapped_column(
        "is_financial", Boolean, default=False, comment="历史兼容字段"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否激活")

    # 排序和层级
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    level: Mapped[int] = mapped_column(Integer, default=1, comment="科目级别")
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("account_subjects.id"), nullable=True)

    # 时间字段
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关系
    category: Mapped["AccountCategory"] = relationship("AccountCategory", back_populates="subjects")
    parent: Mapped[Optional["AccountSubject"]] = relationship("AccountSubject", remote_side="AccountSubject.id")
    financial_data: Mapped[List["FinancialData"]] = relationship("FinancialData", back_populates="subject")
    source_aliases: Mapped[List["AccountSubjectSourceAlias"]] = relationship(
        "AccountSubjectSourceAlias", back_populates="subject"
    )

    __table_args__ = (
        Index("ix_account_subjects_report_type", "report_type"),
        Index("ix_account_subjects_subject_category", "subject_category"),
    )

    def __repr__(self) -> str:
        return f"<AccountSubject {self.code} - {self.name}>"


class AccountSubjectSourceAlias(Base):
    """外部数据源科目别名，映射目标始终为标准科目表。"""
    __tablename__ = "account_subject_source_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("account_subjects.id"), index=True, comment="标准科目ID"
    )
    source: Mapped[str] = mapped_column(String(50), default="sina", comment="数据源代码")
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType), comment="报表类型")
    source_name: Mapped[str] = mapped_column(String(200), comment="来源原始科目名称")
    normalized_name: Mapped[str] = mapped_column(
        String(200), comment="确定性归一化后的来源名称"
    )
    # 空字符串表示不要求报表层级上下文，避免 NULL 唯一约束在 MySQL 中失效。
    context_name: Mapped[str] = mapped_column(
        String(200), default="", comment="来源父级科目名称"
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="映射审核说明")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    subject: Mapped["AccountSubject"] = relationship(
        "AccountSubject", back_populates="source_aliases"
    )

    __table_args__ = (
        UniqueConstraint(
            "source",
            "report_type",
            "source_name",
            "context_name",
            name="uq_subject_source_alias",
        ),
        Index(
            "ix_subject_source_alias_normalized",
            "source",
            "report_type",
            "normalized_name",
            "context_name",
        ),
    )

    def __repr__(self) -> str:
        return f"<AccountSubjectSourceAlias {self.source}:{self.source_name}>"


# ============================================================
# 财务数据模型
# ============================================================

class FinancialData(Base):
    """财务数据存储模型"""
    __tablename__ = "financial_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 关系字段
    company_code: Mapped[str] = mapped_column(String(10), ForeignKey("companies.stock_code"), index=True)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("account_subjects.id"))

    # 编码字段（主要查询字段）
    subject_code: Mapped[str] = mapped_column(String(20), index=True, comment="科目编码")

    # 报表信息
    report_date: Mapped[date] = mapped_column(Date, index=True, comment="报告日期")
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType), comment="报表类型")
    report_period: Mapped[ReportPeriod] = mapped_column(
        Enum(ReportPeriod), default=ReportPeriod.ANNUAL, comment="报告期间"
    )

    # 数据值（支持多种类型）
    value_decimal: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True, comment="数值")
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="文本值")
    value_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="日期值")
    value_boolean: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, comment="布尔值")

    # 数据来源
    data_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="数据来源")
    crawl_task_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="采集任务ID")
    source_subject_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="来源原始科目名称"
    )
    source_context_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="来源父级科目名称"
    )
    subject_match_method: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="科目匹配方法"
    )

    # 时间字段
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关系
    company: Mapped["Company"] = relationship("Company", back_populates="financial_data")
    subject: Mapped["AccountSubject"] = relationship("AccountSubject", back_populates="financial_data")

    __table_args__ = (
        UniqueConstraint("company_code", "subject_id", "report_date", "report_type", name="uq_financial_data"),
        Index("ix_financial_data_company_date", "company_code", "report_date"),
        Index("ix_financial_data_subject_date", "subject_id", "report_date"),
        Index(
            "ix_financial_data_coverage_lookup",
            "company_code",
            "report_type",
            "report_date",
            "subject_code",
        ),
    )

    def __repr__(self) -> str:
        return f"<FinancialData {self.company_code} - {self.subject_code} - {self.report_date}>"


class FinancialMatchIssue(Base):
    """未匹配、歧义或冲突的来源财务科目，供人工补录和审计。"""
    __tablename__ = "financial_match_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("companies.stock_code"), index=True, comment="公司代码"
    )
    report_date: Mapped[date] = mapped_column(Date, index=True, comment="报告日期")
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType), comment="报表类型")
    source: Mapped[str] = mapped_column(String(50), default="sina", comment="数据源代码")
    raw_subject_name: Mapped[str] = mapped_column(String(200), comment="来源原始科目名称")
    context_name: Mapped[str] = mapped_column(
        String(200), default="", comment="来源父级科目名称"
    )
    raw_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 4), nullable=True, comment="来源原始数值"
    )
    issue_type: Mapped[str] = mapped_column(String(50), comment="unmatched/ambiguous/rejected/conflict")
    candidate_subject_codes: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="候选标准科目编码"
    )
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="问题说明")
    crawl_task_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="采集任务ID")
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, comment="出现次数")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    company: Mapped["Company"] = relationship(
        "Company", back_populates="financial_match_issues"
    )

    __table_args__ = (
        UniqueConstraint(
            "company_code",
            "report_date",
            "report_type",
            "source",
            "raw_subject_name",
            "context_name",
            "issue_type",
            name="uq_financial_match_issue",
        ),
        Index(
            "ix_financial_match_issues_lookup",
            "company_code",
            "report_type",
            "report_date",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FinancialMatchIssue {self.company_code} {self.report_type} "
            f"{self.raw_subject_name} {self.issue_type}>"
        )


# ============================================================
# 数据采集模型
# ============================================================

class DataSource(Base):
    """数据源配置模型"""
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), comment="数据源名称")
    code: Mapped[str] = mapped_column(String(50), unique=True, comment="数据源代码")
    base_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="基础URL")
    api_type: Mapped[DataSourceType] = mapped_column(
        Enum(DataSourceType), default=DataSourceType.HTML, comment="API类型"
    )
    headers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="请求头配置")
    rate_limit: Mapped[int] = mapped_column(Integer, default=60, comment="限频(每分钟请求数)")
    timeout: Mapped[int] = mapped_column(Integer, default=30, comment="超时时间(秒)")
    retry_times: Mapped[int] = mapped_column(Integer, default=3, comment="重试次数")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否激活")
    priority: Mapped[int] = mapped_column(Integer, default=1, comment="优先级")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关系
    tasks: Mapped[List["CrawlerTask"]] = relationship("CrawlerTask", back_populates="data_source")

    def __repr__(self) -> str:
        return f"<DataSource {self.code} - {self.name}>"


class CrawlerTask(Base):
    """数据采集任务模型"""
    __tablename__ = "crawler_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_name: Mapped[str] = mapped_column(String(100), comment="任务名称")
    data_source_id: Mapped[int] = mapped_column(Integer, ForeignKey("data_sources.id"))
    data_type: Mapped[CrawlerDataType] = mapped_column(Enum(CrawlerDataType), comment="数据类型")
    target_companies: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, comment="目标公司列表")
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="开始日期")
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="结束日期")

    # 状态信息
    status: Mapped[CrawlerTaskStatus] = mapped_column(
        Enum(CrawlerTaskStatus), default=CrawlerTaskStatus.PENDING, comment="状态"
    )
    progress: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, comment="进度百分比")
    total_count: Mapped[int] = mapped_column(Integer, default=0, comment="总数量")
    success_count: Mapped[int] = mapped_column(Integer, default=0, comment="成功数量")
    error_count: Mapped[int] = mapped_column(Integer, default=0, comment="失败数量")
    error_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="错误日志")
    extra_params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="额外参数")

    # 时间信息
    scheduled_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="计划执行时间")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="开始时间")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="完成时间")

    # 创建信息
    created_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关系
    data_source: Mapped["DataSource"] = relationship("DataSource", back_populates="tasks")

    __table_args__ = (
        Index("ix_crawler_tasks_status_scheduled", "status", "scheduled_time"),
        Index("ix_crawler_tasks_data_type", "data_type"),
    )

    def __repr__(self) -> str:
        return f"<CrawlerTask {self.task_name} - {self.status.value}>"


class QualitativeReport(Base):
    """定性报告表 - 存储从年报/季报 PDF 中提取的结构化 MD&A 数据"""
    __tablename__ = "qualitative_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 关联信息
    company_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("companies.stock_code"), index=True, comment="股票代码"
    )
    report_type: Mapped[str] = mapped_column(
        String(10), comment="报告类型: annual/semi_annual/q1/q3"
    )
    report_period: Mapped[date] = mapped_column(
        Date, index=True, comment="报告期（期末日期）"
    )
    publish_date: Mapped[date] = mapped_column(
        Date, index=True, comment="披露日期"
    )

    # MD&A 结构化提取结果（长文本用 MEDIUMTEXT，避免年报 Markdown 超 64KB）
    overview: Mapped[Optional[str]] = mapped_column(
        LongText, nullable=True, comment="报告期内公司概况"
    )
    revenue_analysis: Mapped[Optional[str]] = mapped_column(
        LongText, nullable=True, comment="收入和利润分析"
    )
    cost_analysis: Mapped[Optional[str]] = mapped_column(
        LongText, nullable=True, comment="成本分析"
    )
    rd_investment: Mapped[Optional[str]] = mapped_column(
        LongText, nullable=True, comment="研发投入分析"
    )
    core_competencies: Mapped[Optional[str]] = mapped_column(
        LongText, nullable=True, comment="核心竞争力分析"
    )
    risk_factors: Mapped[Optional[str]] = mapped_column(
        LongText, nullable=True, comment="风险因素（原文）"
    )
    risk_keywords: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="风险关键词提取（JSON数组）"
    )
    future_outlook: Mapped[Optional[str]] = mapped_column(
        LongText, nullable=True, comment="管理层未来展望"
    )
    capacity_plans: Mapped[Optional[str]] = mapped_column(
        LongText, nullable=True, comment="产能规划/在建工程说明"
    )
    management_discussion: Mapped[Optional[str]] = mapped_column(
        LongText, nullable=True, comment="完整管理层讨论/原始Markdown（可超64KB）"
    )

    # 提取元数据
    source_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="来源URL（巨潮资讯网链接）"
    )
    raw_markdown_length: Mapped[int] = mapped_column(
        Integer, default=0, comment="MinerU 原始 Markdown 长度"
    )
    extraction_method: Mapped[str] = mapped_column(
        String(20), default="mineru", comment="提取方式: mineru/other"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    # 关系
    company: Mapped["Company"] = relationship("Company")

    __table_args__ = (
        UniqueConstraint("company_code", "report_period", "report_type", name="uq_qualitative_report"),
        Index("ix_qualitative_reports_publish_date", "publish_date"),
    )

    def __repr__(self) -> str:
        return f"<QualitativeReport {self.company_code} {self.report_period} {self.report_type}>"


class NewsSentiment(Base):
    """新闻舆情情绪表 - 存储公司新闻的正负面情绪分析"""
    __tablename__ = "news_sentiment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 关联信息
    company_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("companies.stock_code"), index=True, comment="股票代码"
    )

    # 新闻数据
    source: Mapped[str] = mapped_column(String(50), comment="来源: sina/eastmoney/guba")
    title: Mapped[str] = mapped_column(String(500), comment="新闻标题")
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="原文链接")
    publish_date: Mapped[date] = mapped_column(Date, index=True, comment="发布日期")

    # 情绪分析结果
    sentiment_score: Mapped[float] = mapped_column(
        Float, default=0.0, comment="情绪得分 (-1.0 负面 ~ +1.0 正面)"
    )
    sentiment_label: Mapped[str] = mapped_column(
        String(10), default="neutral", comment="情绪标签: positive/negative/neutral"
    )
    keywords: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="关键主题词"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )

    # 关系
    company: Mapped["Company"] = relationship("Company")

    __table_args__ = (
        Index("ix_news_sentiment_company_date", "company_code", "publish_date"),
    )

    def __repr__(self) -> str:
        return f"<NewsSentiment {self.company_code} {self.publish_date} {self.sentiment_label}>"


class IndustryCompetition(Base):
    """行业竞争格局表 - 存储行业集中度、竞争态势等量化指标"""
    __tablename__ = "industry_competitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 关联信息
    industry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("industries.id"), index=True, comment="行业ID"
    )
    calc_date: Mapped[date] = mapped_column(
        Date, server_default=func.now(), comment="计算日期"
    )

    # 集中度指标
    cr3: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="CR3（前三大市占率之和%）")
    cr5: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="CR5（前五大的市占率之和%）")
    hhi: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="HHI 指数")

    # 竞争态势
    gdp_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="行业平均毛利率")
    gdp_std: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="毛利率标准差（越小越同质化）")
    revenue_growth_avg: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="行业平均营收增速%")
    revenue_growth_trend: Mapped[str] = mapped_column(
        String(10), default="stable", comment="增速趋势: accelerating/stable/declining"
    )

    # 产能指标
    capex_growth_avg: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="行业平均资本开支增速%")
    wip_growth_vs_revenue: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="在建工程增速 - 营收增速（正值=扩产快于需求）"
    )

    # 监管关键词计数
    regulatory_keyword_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="监管相关关键词出现次数"
    )
    regulatory_keywords: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="具体关键词列表"
    )

    # 竞争格局判断
    competition_level: Mapped[str] = mapped_column(
        String(20), default="unknown", comment="竞争程度: monopoly/oligopoly/competitive/fierce"
    )
    cycle_phase: Mapped[str] = mapped_column(
        String(20), default="unknown", comment="周期阶段: recovery/expansion/peak/decline"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )

    # 关系
    industry: Mapped["Industry"] = relationship("Industry")

    __table_args__ = (
        Index("ix_industry_competitions_industry_date", "industry_id", "calc_date"),
    )

    def __repr__(self) -> str:
        return f"<IndustryCompetition {self.industry_id} {self.calc_date}>"


class ValuationForecast(Base):
    """估值预测记录表 - 存储RIM/DCF模型的预测数据"""
    __tablename__ = "valuation_forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 关联信息
    company_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("companies.stock_code"), index=True, comment="股票代码"
    )
    valuation_method: Mapped[str] = mapped_column(
        String(20), comment="估值方法: RIM/DCF"
    )
    base_year: Mapped[int] = mapped_column(Integer, comment="基准年份")
    
    # 预测参数
    parameters: Mapped[dict] = mapped_column(JSON, comment="预测参数（JSON格式）")
    
    # 预测数据
    forecast_year: Mapped[int] = mapped_column(Integer, comment="预测年份（相对基准年的偏移量，如1表示T1）")
    forecast_eps: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True, comment="预测EPS")
    forecast_dps: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True, comment="预测DPS")
    forecast_bps: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True, comment="预测BPS")
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    company: Mapped["Company"] = relationship("Company")

    __table_args__ = (
        UniqueConstraint("company_code", "valuation_method", "base_year", "forecast_year", name="uq_valuation_forecast"),
        Index("ix_valuation_forecasts_company_year", "company_code", "base_year"),
        Index("ix_valuation_forecasts_method", "valuation_method"),
    )

    def __repr__(self) -> str:
        return f"<ValuationForecast {self.company_code} {self.valuation_method} Y{self.forecast_year}>"


class CompanySegment(Base):
    """公司经营分部 / 主营构成（供 SOTP 估值）"""
    __tablename__ = "company_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("companies.stock_code"), index=True, comment="股票代码"
    )
    report_period: Mapped[date] = mapped_column(Date, index=True, comment="报告期（期末）")
    report_type: Mapped[str] = mapped_column(
        String(20), default="annual", comment="annual/semi_annual/q1/q3"
    )
    segment_name: Mapped[str] = mapped_column(String(100), comment="分部名称")
    segment_type: Mapped[str] = mapped_column(
        String(20), default="product", comment="product/region/other"
    )
    revenue: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(24, 2), nullable=True, comment="分部营业收入（元）"
    )
    operating_income: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(24, 2), nullable=True, comment="分部营业利润（元）"
    )
    ebitda: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(24, 2), nullable=True, comment="分部EBITDA（元，可空）"
    )
    revenue_yoy: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True, comment="营收同比"
    )
    op_margin: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True, comment="营业利润率"
    )
    currency: Mapped[str] = mapped_column(String(10), default="CNY", comment="币种")
    source: Mapped[str] = mapped_column(
        String(30), default="manual", comment="cninfo_pdf/eastmoney/manual/llm"
    )
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    confidence: Mapped[str] = mapped_column(
        String(10), default="medium", comment="high/medium/low"
    )
    raw_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="原文片段")
    multiple_override: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True, comment="手工倍数覆盖"
    )
    multiple_type: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="ev_ebitda/ev_revenue"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    company: Mapped["Company"] = relationship("Company")

    __table_args__ = (
        UniqueConstraint(
            "company_code",
            "report_period",
            "segment_name",
            "segment_type",
            name="uq_company_segment",
        ),
        Index("ix_company_segments_code_period", "company_code", "report_period"),
    )

    def __repr__(self) -> str:
        return f"<CompanySegment {self.company_code} {self.segment_name} {self.report_period}>"


class FinancialCoverageSnapshot(Base):
    """财务数据覆盖率扫描快照"""
    __tablename__ = "financial_coverage_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 扫描范围签名，便于按相同 years/report_types/status 取最新快照
    scope_key: Mapped[str] = mapped_column(String(120), index=True, comment="years|reports|status 签名")
    years: Mapped[list] = mapped_column(JSON, comment="扫描年份列表")
    report_types: Mapped[list] = mapped_column(JSON, comment="报表类型列表")
    status_filter: Mapped[str] = mapped_column(String(20), default="active", comment="公司状态过滤")
    source: Mapped[str] = mapped_column(
        String(30), default="manual_scan", comment="manual_scan/post_repair/api"
    )
    trigger_task_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True, comment="触发本次扫描的采集任务ID"
    )

    company_count: Mapped[int] = mapped_column(Integer, default=0)
    matrix_total: Mapped[int] = mapped_column(Integer, default=0)
    complete_cells: Mapped[int] = mapped_column(Integer, default=0)
    partial_cells: Mapped[int] = mapped_column(Integer, default=0)
    missing_cells: Mapped[int] = mapped_column(Integer, default=0)
    gap_company_count: Mapped[int] = mapped_column(Integer, default=0)
    coverage_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), default=0)

    summary: Mapped[dict] = mapped_column(JSON, comment="汇总统计")
    gap_companies: Mapped[list] = mapped_column(JSON, comment="缺口公司代码列表")
    # 公司矩阵明细可能较大，用 LongText 兼容 MySQL
    companies_payload: Mapped[Optional[str]] = mapped_column(
        LongText, nullable=True, comment="公司矩阵 JSON 字符串"
    )
    core_subjects: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="核心科目定义")

    scan_duration_ms: Mapped[int] = mapped_column(Integer, default=0, comment="扫描耗时毫秒")
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_coverage_snapshots_scope_created", "scope_key", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<FinancialCoverageSnapshot {self.id} {self.scope_key} {self.coverage_rate}>"


class FinancialCoverageSnapshotCompany(Base):
    """财务覆盖率快照中的单家公司明细，用于数据库分页。"""
    __tablename__ = "financial_coverage_snapshot_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("financial_coverage_snapshots.id"),
        nullable=False,
    )
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(100), nullable=False)
    overall_status: Mapped[str] = mapped_column(String(12), nullable=False)
    coverage_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), default=0)
    complete_cells: Mapped[int] = mapped_column(Integer, default=0)
    partial_cells: Mapped[int] = mapped_column(Integer, default=0)
    missing_cells: Mapped[int] = mapped_column(Integer, default=0)
    expected_cells: Mapped[int] = mapped_column(Integer, default=0)
    company_payload: Mapped[dict] = mapped_column(JSON, comment="单家公司覆盖矩阵")

    __table_args__ = (
        UniqueConstraint("snapshot_id", "stock_code", name="uq_coverage_snapshot_company"),
        Index(
            "ix_coverage_snapshot_company_page",
            "snapshot_id",
            "overall_status",
            "stock_code",
        ),
        Index("ix_coverage_snapshot_company_code", "snapshot_id", "stock_code"),
    )

    def __repr__(self) -> str:
        return (
            f"<FinancialCoverageSnapshotCompany {self.snapshot_id} "
            f"{self.stock_code} {self.overall_status}>"
        )
