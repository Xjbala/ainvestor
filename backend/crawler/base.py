# -*- coding: utf-8 -*-
"""
爬虫基础服务

提供爬虫的通用功能和抽象接口。
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..persistence.financial_models import (
    CrawlerTask, CrawlerTaskStatus, CrawlerDataType,
    Company, FinancialData, DataSource
)

logger = logging.getLogger(__name__)

# 任务明细日志最大保留长度，避免撑爆 Text 字段
_TASK_LOG_MAX_CHARS = 100_000


def format_task_log_line(message: str, level: str = "INFO") -> str:
    """格式化单条任务日志行"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{ts}] [{level}] {message}"


def merge_task_log(existing: Optional[str], message: str, level: str = "INFO") -> str:
    """
    将新日志行合并到任务日志文本中。

    超过上限时截断头部，保留最近内容。
    """
    line = format_task_log_line(message, level)
    text = f"{existing}\n{line}" if existing else line
    if len(text) > _TASK_LOG_MAX_CHARS:
        text = "...(earlier logs truncated)...\n" + text[-_TASK_LOG_MAX_CHARS:]
    return text


async def append_task_log(
    session: AsyncSession,
    task: CrawlerTask,
    message: str,
    level: str = "INFO",
    commit: bool = True,
) -> None:
    """
    向任务写入明细日志（同时输出到应用 logger）。

    日志写入 CrawlerTask.error_log 字段（作为任务明细日志使用）。
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    task_tag = (task.id or "")[:8]
    logger.log(log_level, f"[Task {task_tag}] {message}")
    task.error_log = merge_task_log(task.error_log, message, level)
    if commit:
        await session.commit()


class CrawlerService(ABC):
    """
    爬虫服务基类

    所有具体爬虫（新浪、网易等）需继承此类并实现抽象方法。
    """

    def __init__(
        self,
        session: AsyncSession,
        data_source_code: str,
        rate_limit: int = 60,
        timeout: int = 30,
        retry_times: int = 3,
    ):
        """
        初始化爬虫服务

        Args:
            session: 数据库异步会话
            data_source_code: 数据源代码
            rate_limit: 每分钟请求限制
            timeout: 请求超时时间(秒)
            retry_times: 重试次数
        """
        self.session = session
        self.data_source_code = data_source_code
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.retry_times = retry_times

        # 请求间隔（秒）
        self._request_interval = 60.0 / rate_limit

        # HTTP 客户端
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            raise RuntimeError("CrawlerService must be used within async context manager")
        return self._client

    async def fetch(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        发起 HTTP GET 请求

        包含自动重试和限流逻辑。

        Args:
            url: 请求URL
            headers: 请求头
            params: URL参数

        Returns:
            响应内容文本，失败返回 None
        """
        for attempt in range(self.retry_times):
            try:
                response = await self.client.get(url, headers=headers, params=params)
                response.raise_for_status()

                # 请求成功后等待限流间隔
                await asyncio.sleep(self._request_interval)

                return response.text

            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error {e.response.status_code} for {url}, attempt {attempt + 1}")
            except httpx.TimeoutException:
                logger.warning(f"Timeout for {url}, attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"Request error for {url}: {e}")

            # 重试前等待
            if attempt < self.retry_times - 1:
                await asyncio.sleep(2 ** attempt)  # 指数退避

        return None

    async def fetch_json(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        发起 HTTP GET 请求并解析 JSON

        Args:
            url: 请求URL
            headers: 请求头
            params: URL参数

        Returns:
            解析后的 JSON 对象，失败返回 None
        """
        for attempt in range(self.retry_times):
            try:
                response = await self.client.get(url, headers=headers, params=params)
                response.raise_for_status()

                # 请求成功后等待限流间隔
                await asyncio.sleep(self._request_interval)

                return response.json()

            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error {e.response.status_code} for {url}, attempt {attempt + 1}")
            except httpx.TimeoutException:
                logger.warning(f"Timeout for {url}, attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"Request error for {url}: {e}")

            # 重试前等待
            if attempt < self.retry_times - 1:
                await asyncio.sleep(2 ** attempt)

        return None

    @abstractmethod
    async def crawl_company_list(self) -> List[Dict[str, Any]]:
        """
        爬取公司列表

        Returns:
            公司信息列表
        """
        pass

    @abstractmethod
    async def crawl_financial_report(
        self,
        stock_code: str,
        report_type: str,
        year: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        爬取财务报表数据

        Args:
            stock_code: 股票代码
            report_type: 报表类型 (BS/IS/CF)
            year: 年份（可选）

        Returns:
            财务报表数据
        """
        pass

    async def append_log(
        self,
        task: CrawlerTask,
        message: str,
        level: str = "INFO",
        commit: bool = True,
    ) -> None:
        """向当前任务追加明细日志"""
        await append_task_log(self.session, task, message, level=level, commit=commit)

    async def update_task_progress(
        self,
        task: CrawlerTask,
        success_count: int,
        error_count: int,
        total_count: int,
        error_log: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        """
        更新任务进度

        Args:
            task: 爬虫任务
            success_count: 成功数量
            error_count: 失败数量
            total_count: 总数量
            error_log: 错误日志（兼容旧参数，写入明细）
            detail: 进度明细说明（写入明细日志）
        """
        task.success_count = success_count
        task.error_count = error_count
        task.total_count = total_count
        # Numeric(5,2) 上限 999.99；进度钳制在 [0, 100]
        raw_progress = (success_count + error_count) / max(total_count, 1) * 100
        task.progress = Decimal(str(min(100.0, max(0.0, raw_progress))))

        if error_log:
            task.error_log = merge_task_log(task.error_log, error_log, "ERROR")
        if detail:
            task.error_log = merge_task_log(
                task.error_log,
                f"进度 {task.progress:.1f}% | 成功={success_count} 失败={error_count} 总数={total_count} | {detail}",
                "INFO",
            )

        await self.session.commit()

    async def start_task(self, task: CrawlerTask) -> None:
        """标记任务开始"""
        task.status = CrawlerTaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.error_log = merge_task_log(
            task.error_log,
            f"任务开始执行 | 类型={task.data_type.value if task.data_type else '-'} | "
            f"目标公司数={len(task.target_companies or [])}",
            "INFO",
        )
        await self.session.commit()

    async def complete_task(self, task: CrawlerTask, success: bool = True) -> None:
        """标记任务完成"""
        task.status = CrawlerTaskStatus.SUCCESS if success else CrawlerTaskStatus.FAILED
        task.completed_at = datetime.utcnow()
        task.progress = Decimal("100.00")
        summary = (
            f"任务{'成功' if success else '失败'}结束 | "
            f"成功={task.success_count} 失败={task.error_count} 总数={task.total_count}"
        )
        task.error_log = merge_task_log(task.error_log, summary, "INFO" if success else "ERROR")
        await self.session.commit()

    async def cancel_task(self, task: CrawlerTask) -> None:
        """取消任务"""
        task.status = CrawlerTaskStatus.CANCELLED
        task.completed_at = datetime.utcnow()
        task.error_log = merge_task_log(task.error_log, "任务已取消", "WARNING")
        await self.session.commit()


def parse_decimal(value: Any) -> Optional[Decimal]:
    """
    解析数值为 Decimal

    处理各种格式的数值字符串，包括带单位的情况。
    """
    if value is None or value == "" or value == "--" or value == "-":
        return None

    if isinstance(value, (int, float)):
        return Decimal(str(value))

    if isinstance(value, Decimal):
        return value

    if isinstance(value, str):
        # 移除千分位逗号
        value = value.replace(",", "")

        # 处理单位
        multiplier = 1
        if value.endswith("万"):
            multiplier = 10000
            value = value[:-1]
        elif value.endswith("亿"):
            multiplier = 100000000
            value = value[:-1]
        elif value.endswith("%"):
            multiplier = 0.01
            value = value[:-1]

        try:
            return Decimal(value) * Decimal(str(multiplier))
        except Exception:
            return None

    return None
