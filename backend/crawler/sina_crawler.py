# -*- coding: utf-8 -*-
"""
新浪财经爬虫服务

移植自 leofun 项目的新浪财经数据爬取逻辑。
提供股票列表、财务报表等数据采集能力。
"""

import asyncio
import logging
import re
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .base import CrawlerService, parse_decimal
from .subject_matching import SinaSubjectMatcher
from ..persistence.db import async_session_factory
from ..persistence.financial_models import (
    Company,
    AccountSubject,
    AccountSubjectSourceAlias,
    FinancialData,
    FinancialMatchIssue,
    ReportType,
    ReportPeriod,
    Exchange,
    Industry,
)
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 新浪财经 JSON API 地址
SINA_JSON_API_URL = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"

# 分区标题 / 纯结构行，不落库
_SECTION_TITLES = {
    "流动资产",
    "非流动资产",
    "流动负债",
    "非流动负债",
    "所有者权益",
    "经营活动产生的现金流量",
    "投资活动产生的现金流量",
    "筹资活动产生的现金流量",
}


class SinaCrawlerService(CrawlerService):
    """
    新浪财经爬虫服务

    数据来源：
    - 股票列表：新浪财经行情中心
    - 财务报表：新浪财经财务数据
    """

    # 新浪财经 API 地址
    STOCK_LIST_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    REPORT_URL = "https://money.finance.sina.com.cn/corp/go.php/vFD_FinancialGuideLine/stockid/{stock_code}/displaytype/4.phtml"

    # 财务数据 API (JSON)
    # source: fzb=资产负债表, lrb=利润表, llb=现金流量表
    # page/num 支持分页；num=50 可覆盖较完整历史
    REPORT_JSON_URL = (
        SINA_JSON_API_URL
        + "?paperCode={paper_code}&source={source}&type=0&page={page}&num={num}"
    )
    REPORT_PAGE_SIZE = 50
    REPORT_MAX_PAGES = 5

    # 请求头
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn/",
    }

    def __init__(self, session, **kwargs):
        super().__init__(session, data_source_code="sina", **kwargs)
        self._subject_cache_loaded = False
        self._subject_cache_lock = asyncio.Lock()
        self._subject_matcher: Optional[SinaSubjectMatcher] = None

    async def crawl_company_list(self) -> List[Dict[str, Any]]:
        """
        爬取 A 股公司列表

        Returns:
            公司信息列表，每个公司包含:
            - stock_code: 股票代码
            - stock_name: 股票名称
            - exchange: 交易所 (sh/sz)
            - current_price: 当前价格
            - change_percent: 涨跌幅
        """
        companies = []

        # 爬取沪市股票
        sh_companies = await self._crawl_stock_list("sh_a")
        companies.extend(sh_companies)

        # 爬取深市股票
        sz_companies = await self._crawl_stock_list("sz_a")
        companies.extend(sz_companies)

        logger.info(f"Crawled {len(companies)} companies from Sina Finance")
        return companies

    async def save_companies(self, companies: List[Dict[str, Any]]):
        """保存公司列表到数据库"""
        if not companies:
            return
        
        async with async_session_factory() as session:
            # 获取或创建交易所
            exchanges = {}
            for ex_code in ["sh", "sz"]:
                stmt = select(Exchange).where(Exchange.code == ex_code)
                result = await session.execute(stmt)
                ex = result.scalar_one_or_none()
                if not ex:
                    ex = Exchange(code=ex_code, name="上海证券交易所" if ex_code == "sh" else "深圳证券交易所", country="中国")
                    session.add(ex)
                    await session.flush()
                exchanges[ex_code] = ex.id

            for item in companies:
                stock_code = item["stock_code"]
                stmt = select(Company).where(Company.stock_code == stock_code)
                result = await session.execute(stmt)
                company = result.scalars().first()
                
                if company:
                    company.stock_name = item.get("stock_name", company.stock_name)
                    company.pe_ratio = item.get("pe_ratio", company.pe_ratio)
                    company.pb_ratio = item.get("pb_ratio", company.pb_ratio)
                    company.market_cap = item.get("market_cap", company.market_cap)
                else:
                    company = Company(
                        stock_code=stock_code,
                        stock_name=item.get("stock_name"),
                        exchange_id=exchanges.get(item.get("exchange", "sh")),
                        company_name=item.get("stock_name"), # 简化处理
                        status="active",
                        pe_ratio=item.get("pe_ratio"),
                        pb_ratio=item.get("pb_ratio"),
                        market_cap=item.get("market_cap")
                    )
                    session.add(company)
            
            await session.commit()
            logger.info(f"Saved {len(companies)} companies to DB")

    async def _crawl_stock_list(
        self,
        node: str,
        page: int = 1,
        num: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        爬取单个市场的股票列表

        Args:
            node: 市场节点 (sh_a/sz_a)
            page: 页码
            num: 每页数量

        Returns:
            股票列表
        """
        params = {
            "node": node,
            "page": page,
            "num": num,
            "_s_r_a": "auto",
        }

        data = await self.fetch_json(self.STOCK_LIST_URL, headers=self.HEADERS, params=params)

        if not data:
            logger.warning(f"Failed to fetch stock list for {node}")
            return []

        companies = []
        for item in data:
            try:
                # 解析股票代码
                symbol = item.get("symbol", "")
                exchange = "sh" if symbol.startswith("sh") else "sz"
                stock_code = symbol[2:] if len(symbol) > 2 else symbol

                companies.append({
                    "stock_code": stock_code,
                    "stock_name": item.get("name", ""),
                    "exchange": exchange,
                    "current_price": parse_decimal(item.get("trade")),
                    "change_percent": parse_decimal(item.get("changepercent")),
                    "volume": parse_decimal(item.get("volume")),
                    "turnover": parse_decimal(item.get("amount")),
                    "pe_ratio": parse_decimal(item.get("pe")),
                    "pb_ratio": parse_decimal(item.get("pb")),
                    "market_cap": parse_decimal(item.get("mktcap")),
                })
            except Exception as e:
                logger.error(f"Failed to parse stock item: {e}")
                continue

        return companies

    async def crawl_financial_report(
        self,
        stock_code: str,
        report_type: str,
        year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        爬取财务报表数据 (JSON API)

        Args:
            stock_code: 股票代码
            report_type: 报表类型 (BS/IS/CF)
            year: 目标年份 (如果指定，仅返回该年份数据)

        Returns:
            财务数据列表
        """
        source_map = {
            "BS": "fzb",
            "IS": "lrb",
            "CF": "llb",
        }

        source = source_map.get(report_type)
        if not source:
            logger.error(f"Unknown report type: {report_type}")
            return []

        # 确定交易所前缀
        exchange_prefix = "sz" if stock_code.startswith(("0", "3")) else "sh"
        paper_code = f"{exchange_prefix}{stock_code}"

        financial_data_list: List[Dict[str, Any]] = []
        seen_periods: set = set()
        report_count = None

        for page in range(1, self.REPORT_MAX_PAGES + 1):
            url = self.REPORT_JSON_URL.format(
                paper_code=paper_code,
                source=source,
                page=page,
                num=self.REPORT_PAGE_SIZE,
            )
            logger.info(
                f"[Sina] 拉取财报 {stock_code} type={report_type} year={year or 'all'} "
                f"paper={paper_code} page={page} url={url}"
            )
            data = await self.fetch_json(url, headers=self.HEADERS)

            if not data or "result" not in data:
                logger.warning(
                    f"[Sina] 拉取失败 {stock_code} {report_type} page={page}: 无有效响应"
                )
                break

            result = data["result"]
            if result.get("status", {}).get("code") != 0:
                logger.error(
                    f"[Sina] API 错误 {stock_code} {report_type} page={page}: "
                    f"{result.get('status', {}).get('msg')}"
                )
                break

            data_section = result.get("data", {}) or {}
            if report_count is None:
                report_count = data_section.get("report_count")

            page_items, page_periods = self._parse_report_section(
                data_section=data_section,
                stock_code=stock_code,
                report_type=report_type,
                year=year,
            )
            if not page_periods:
                # 无更多期数
                break

            new_periods = [p for p in page_periods if p not in seen_periods]
            if not new_periods and page > 1:
                break

            for p in page_periods:
                seen_periods.add(p)
            financial_data_list.extend(page_items)

            logger.info(
                f"[Sina] {stock_code} {report_type} page={page} "
                f"本期={len(page_periods)} 累计期数={len(seen_periods)} "
                f"累计科目行={len(financial_data_list)} report_count={report_count}"
            )

            # 已拉全，或本页不足一页，停止
            if report_count and len(seen_periods) >= int(report_count):
                break
            if len(page_periods) < self.REPORT_PAGE_SIZE:
                break

        if financial_data_list:
            periods = sorted(seen_periods)
            logger.info(
                f"[Sina] {stock_code} {report_type} 解析完成: "
                f"{len(financial_data_list)} 条科目, 报告期数={len(periods)}, "
                f"范围={periods[0]}~{periods[-1]}"
            )
        else:
            logger.warning(f"[Sina] {stock_code} {report_type} 解析结果为空")
        return financial_data_list

    def _parse_report_section(
        self,
        data_section: Dict[str, Any],
        stock_code: str,
        report_type: str,
        year: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """解析单页 API 响应中的报表数据。"""
        financial_data_list: List[Dict[str, Any]] = []
        periods: List[str] = []

        # 处理 report_list 结构 (2022 API)
        if "report_list" in data_section:
            report_list = data_section.get("report_list") or {}
            period_keys = list(report_list.keys())
            for date_key, date_payload in report_list.items():
                if year and not str(date_key).startswith(str(year)):
                    continue
                if len(str(date_key)) != 8:
                    continue

                report_date_str = f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}"
                periods.append(report_date_str)

                items = (date_payload or {}).get("data", []) or []
                last_major = ""
                for item in items:
                    subject_name = (item.get("item_title") or "").strip()
                    if not subject_name or subject_name in _SECTION_TITLES:
                        continue
                    item_val = item.get("item_value")
                    display_type = item.get("item_display_type")
                    # 记录最近主科目，用于区分同名明细（如财务费用下的利息收入）
                    try:
                        dt_int = int(display_type) if display_type is not None else 99
                    except (TypeError, ValueError):
                        dt_int = 99
                    if dt_int in (1, 2, 6) and subject_name not in (
                        "利息收入",
                        "利息费用",
                        "利息支出",
                    ):
                        last_major = subject_name

                    source_context_name = last_major
                    # 新浪现金流总额行(display_type=7)不属于上一个主科目。
                    if report_type == "CF" and dt_int == 7:
                        source_context_name = subject_name

                    parsed_val = self._parse_financial_value(
                        None if item_val is None else str(item_val)
                    )
                    if parsed_val is not None:
                        financial_data_list.append({
                            "stock_code": stock_code,
                            "subject_name": subject_name,
                            "source_context_name": source_context_name,
                            "report_date": report_date_str,
                            "report_type": report_type,
                            "value": parsed_val,
                            "display_type": display_type,
                            "raw_subject_name": subject_name,
                        })
            return financial_data_list, periods

        # 降级方案：旧版 report_data 结构
        report_dates: List[str] = []
        if "report_date" in data_section:
            for date_info in data_section.get("report_date") or []:
                date_val = date_info.get("date_value", "")
                if len(date_val) == 8:
                    formatted_date = f"{date_val[:4]}-{date_val[4:6]}-{date_val[6:8]}"
                    report_dates.append(formatted_date)

        if "report_data" in data_section:
            for report in data_section.get("report_data") or []:
                subject_name = (report.get("subject_name") or "").strip()
                if not subject_name or subject_name in _SECTION_TITLES:
                    continue
                values = report.get("values", []) or []
                for idx, val in enumerate(values):
                    if idx >= len(report_dates):
                        continue
                    report_date_str = report_dates[idx]
                    if year and not report_date_str.startswith(str(year)):
                        continue
                    parsed_val = self._parse_financial_value(str(val))
                    if parsed_val is not None:
                        financial_data_list.append({
                            "stock_code": stock_code,
                            "subject_name": subject_name,
                            "source_context_name": "",
                            "report_date": report_date_str,
                            "report_type": report_type,
                            "value": parsed_val,
                            "raw_subject_name": subject_name,
                        })
            periods = list(report_dates)
            if year:
                periods = [p for p in periods if p.startswith(str(year))]

        return financial_data_list, periods

    def _parse_financial_value(self, value_text: str) -> Optional[Decimal]:
        """解析财务数值"""
        if not value_text or value_text in ["--", "---", "N/A", "n/a", "", " ", "null", "None"]:
            return None
        try:
            # 清理数值文本
            cleaned = value_text.replace(",", "").strip()
            return Decimal(cleaned)
        except Exception:
            return None

    async def save_to_db(
        self,
        financial_data_list: List[Dict[str, Any]],
        crawl_task_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """保存财务数据，并返回标准科目匹配质量汇总。"""
        if not financial_data_list:
            return self._empty_save_summary()

        # 批量采集并发运行时不能复用引擎会话；每次落库使用独立会话。
        async with async_session_factory() as session:
            return await self._persist_financial_data(
                session, financial_data_list, crawl_task_id=crawl_task_id
            )

    @staticmethod
    def _empty_save_summary() -> Dict[str, int]:
        return {
            "input_rows": 0,
            "matched_rows": 0,
            "inserted_rows": 0,
            "updated_rows": 0,
            "unmatched_rows": 0,
            "ambiguous_rows": 0,
            "rejected_rows": 0,
            "conflict_rows": 0,
        }

    async def _persist_financial_data(
        self,
        session,
        financial_data_list: List[Dict[str, Any]],
        crawl_task_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """在独立 session 上执行财务数据落库和匹配问题审计。"""
        summary = self._empty_save_summary()
        summary["input_rows"] = len(financial_data_list)
        stock_code = financial_data_list[0]["stock_code"]

        company = (
            await session.execute(
                select(Company).where(Company.stock_code == stock_code)
            )
        ).scalar_one_or_none()
        if not company:
            logger.warning("Company %s not found in DB", stock_code)
            return summary

        await self._ensure_subject_cache(session)
        if self._subject_matcher is None:
            raise RuntimeError("Sina standard subject cache was not initialized")

        processed_items: Dict[Tuple[date, int, str], Dict[str, Any]] = {}
        issue_specs: List[Dict[str, Any]] = []
        report_dates_seen: set[date] = set()

        for data in financial_data_list:
            subject_name = str(data.get("subject_name") or "")
            report_type = str(data.get("report_type") or "").upper()
            context_name = str(data.get("source_context_name") or "")
            report_date = date.fromisoformat(data["report_date"])
            display_type = data.get("display_type")
            match = self._subject_matcher.match(subject_name, report_type, context_name)

            if not match.matched:
                issue_specs.append({
                    "report_date": report_date,
                    "report_type": report_type,
                    "raw_subject_name": str(data.get("raw_subject_name") or subject_name),
                    "context_name": context_name,
                    "raw_value": data.get("value"),
                    "issue_type": match.issue_type or "unmatched",
                    "candidate_subject_codes": list(match.candidate_subject_codes) or None,
                    "detail": match.detail,
                })
                summary[f"{match.issue_type or 'unmatched'}_rows"] = (
                    summary.get(f"{match.issue_type or 'unmatched'}_rows", 0) + 1
                )
                continue

            subject = match.subject
            summary["matched_rows"] += 1
            report_dates_seen.add(report_date)
            key = (report_date, subject.id, report_type)
            quality = self._match_quality(match.method or "", display_type)
            candidate = {
                "data": data,
                "subject": subject,
                "match_method": match.method,
                "quality": quality,
            }
            existing_candidate = processed_items.get(key)
            if existing_candidate is None:
                processed_items[key] = candidate
                continue

            previous_value = existing_candidate["data"].get("value")
            current_value = data.get("value")
            if previous_value != current_value:
                issue_specs.append({
                    "report_date": report_date,
                    "report_type": report_type,
                    "raw_subject_name": str(data.get("raw_subject_name") or subject_name),
                    "context_name": context_name,
                    "raw_value": current_value,
                    "issue_type": "conflict",
                    "candidate_subject_codes": [subject.code],
                    "detail": (
                        f"同报告期标准科目 {subject.code} 存在不同来源数值: "
                        f"{previous_value} / {current_value}"
                    ),
                })
                summary["conflict_rows"] += 1
            if quality < existing_candidate["quality"]:
                processed_items[key] = candidate

        await self._record_match_issues(
            session, stock_code, issue_specs, crawl_task_id=crawl_task_id
        )
        if not processed_items:
            await session.commit()
            logger.warning(
                "No safe subject matches for %s (input=%s unmatched=%s ambiguous=%s rejected=%s)",
                stock_code,
                summary["input_rows"],
                summary["unmatched_rows"],
                summary["ambiguous_rows"],
                summary["rejected_rows"],
            )
            return summary

        existing_map: Dict[Tuple[date, int, str], FinancialData] = {}
        date_list = sorted(report_dates_seen)
        for offset in range(0, len(date_list), 40):
            batch_dates = date_list[offset: offset + 40]
            rows = (
                await session.execute(
                    select(FinancialData).where(
                        FinancialData.company_code == stock_code,
                        FinancialData.report_date.in_(batch_dates),
                    )
                )
            ).scalars().all()
            for row in rows:
                report_type = str(getattr(row.report_type, "value", row.report_type))
                existing_map[(row.report_date, row.subject_id, report_type)] = row

        for (report_date, subject_id, report_type), item in processed_items.items():
            data = item["data"]
            subject = item["subject"]
            existing = existing_map.get((report_date, subject_id, report_type))
            values = {
                "subject_code": subject.code,
                "report_period": self._get_report_period(report_date),
                "value_decimal": data["value"],
                "data_source": "sina",
                "crawl_task_id": crawl_task_id,
                "source_subject_name": str(data.get("raw_subject_name") or data["subject_name"]),
                "source_context_name": str(data.get("source_context_name") or "") or None,
                "subject_match_method": item["match_method"],
            }
            if existing:
                for field, value in values.items():
                    setattr(existing, field, value)
                summary["updated_rows"] += 1
            else:
                session.add(
                    FinancialData(
                        company_code=stock_code,
                        subject_id=subject_id,
                        report_date=report_date,
                        report_type=ReportType(report_type),
                        **values,
                    )
                )
                summary["inserted_rows"] += 1

        await session.commit()
        logger.info(
            "[Sina] %s match summary: input=%s matched=%s inserted=%s updated=%s "
            "unmatched=%s ambiguous=%s rejected=%s conflict=%s",
            stock_code,
            summary["input_rows"],
            summary["matched_rows"],
            summary["inserted_rows"],
            summary["updated_rows"],
            summary["unmatched_rows"],
            summary["ambiguous_rows"],
            summary["rejected_rows"],
            summary["conflict_rows"],
        )
        return summary

    async def _record_match_issues(
        self,
        session,
        stock_code: str,
        issue_specs: List[Dict[str, Any]],
        crawl_task_id: Optional[str],
    ) -> None:
        """按问题唯一键累计出现次数，保留首次与最近发现时间。"""
        grouped_specs: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        for spec in issue_specs:
            key = (
                spec["report_date"],
                spec["report_type"],
                spec["raw_subject_name"],
                spec["context_name"],
                spec["issue_type"],
            )
            if key not in grouped_specs:
                grouped_specs[key] = {**spec, "count": 1}
            else:
                grouped_specs[key]["count"] += 1

        for spec in grouped_specs.values():
            existing = (
                await session.execute(
                    select(FinancialMatchIssue).where(
                        FinancialMatchIssue.company_code == stock_code,
                        FinancialMatchIssue.report_date == spec["report_date"],
                        FinancialMatchIssue.report_type == ReportType(spec["report_type"]),
                        FinancialMatchIssue.source == "sina",
                        FinancialMatchIssue.raw_subject_name == spec["raw_subject_name"],
                        FinancialMatchIssue.context_name == spec["context_name"],
                        FinancialMatchIssue.issue_type == spec["issue_type"],
                    )
                )
            ).scalar_one_or_none()
            if existing:
                existing.occurrence_count += spec["count"]
                existing.raw_value = spec["raw_value"]
                existing.candidate_subject_codes = spec["candidate_subject_codes"]
                existing.detail = spec["detail"]
                existing.crawl_task_id = crawl_task_id
                continue
            session.add(
                FinancialMatchIssue(
                    company_code=stock_code,
                    report_date=spec["report_date"],
                    report_type=ReportType(spec["report_type"]),
                    source="sina",
                    raw_subject_name=spec["raw_subject_name"],
                    context_name=spec["context_name"],
                    raw_value=spec["raw_value"],
                    issue_type=spec["issue_type"],
                    candidate_subject_codes=spec["candidate_subject_codes"],
                    detail=spec["detail"],
                    crawl_task_id=crawl_task_id,
                    occurrence_count=spec["count"],
                )
            )

    @staticmethod
    def _display_priority(display_type: Any) -> int:
        """display_type 越小优先级越高。主科目(2/6/1/7)优于明细(3)。"""
        try:
            dt = int(display_type) if display_type is not None else 99
        except (TypeError, ValueError):
            return 99
        if dt in (6, 7):
            return 1
        if dt == 2:
            return 2
        if dt == 1:
            return 3
        if dt == 3:
            return 5
        return 4

    def _match_quality(self, match_method: str, display_type: Any) -> tuple:
        """同一标准科目重复行时，按确定性匹配级别再比较展示层级。"""
        rank = {
            "context_alias_exact": 0,
            "name_exact": 1,
            "sina_name_exact": 2,
            "source_alias_exact": 3,
            "normalized_exact": 4,
        }.get(match_method, 99)
        return rank, self._display_priority(display_type)

    def _get_report_period(self, report_date: date) -> ReportPeriod:
        """根据报告日期确定报告期间"""
        month = report_date.month
        if month == 3:
            return ReportPeriod.Q1
        if month == 6:
            return ReportPeriod.SEMI_ANNUAL
        if month == 9:
            return ReportPeriod.Q3
        return ReportPeriod.ANNUAL

    async def _ensure_subject_cache(self, session) -> None:
        """从标准科目表和审核后的来源别名加载只读匹配缓存。"""
        if self._subject_cache_loaded:
            return
        async with self._subject_cache_lock:
            if self._subject_cache_loaded:
                return
            subjects = (await session.execute(select(AccountSubject))).scalars().all()
            aliases = (
                await session.execute(
                    select(AccountSubjectSourceAlias)
                    .options(selectinload(AccountSubjectSourceAlias.subject))
                    .where(
                        AccountSubjectSourceAlias.source == "sina",
                        AccountSubjectSourceAlias.is_active == True,
                    )
                )
            ).scalars().all()
            self._subject_matcher = SinaSubjectMatcher(subjects, aliases)
            self._subject_cache_loaded = True
            logger.info(
                "[Sina] 标准科目缓存加载完成: subjects=%s, sina_aliases=%s",
                len(subjects),
                len(aliases),
            )

    async def _match_subject(
        self,
        session,
        subject_name: str,
        report_type: str,
        context_name: str = "",
    ) -> Optional[AccountSubject]:
        """兼容旧调用，返回安全匹配到的标准科目。"""
        await self._ensure_subject_cache(session)
        if self._subject_matcher is None:
            return None
        return self._subject_matcher.match(subject_name, report_type, context_name).subject

    async def crawl_stock_price(
        self,
        stock_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        爬取股票历史价格

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            历史价格列表
        """
        # 简化实现
        # 实际需要调用新浪历史行情接口
        logger.info(f"Crawling stock price for {stock_code}")
        return []

    async def _fetch_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        使用新浪hq.sinajs.cn接口获取实时行情数据
        
        这个接口比HTML解析更简单、更可靠，返回格式为：
        var hq_str_sz000001="股票名称,开盘,昨收,现价,最高,最低,买一,卖一,成交量,成交额,..."
        var hq_str_sz000001_i="指标数据,包含PE、PB等"
        
        Args:
            stock_code: 股票代码
            
        Returns:
            包含价格等信息的字典，失败返回None
        """
        try:
            # 确定交易所前缀
            exchange_prefix = "sz" if stock_code.startswith(("0", "3")) else "sh"
            
            # 新浪综合行情API：获取实时行情、指标数据
            url = f"https://hq.sinajs.cn/rn={int(asyncio.get_event_loop().time())}&list={exchange_prefix}{stock_code},{exchange_prefix}{stock_code}_i"
            
            headers = {
                "Referer": f"https://finance.sina.com.cn/realstock/company/{exchange_prefix}{stock_code}/nc.shtml",
                "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36"
            }
            
            content = await self.fetch(url, headers=headers)
            if not content:
                return None
            
            # 解析返回的JavaScript格式数据
            # 有两行数据：实时行情、指标数据
            import re
            
            result = {
                'current_price': None,
                'open_price': None,
                'close_price': None,
                'high_price': None,
                'low_price': None,
                'volume': None,
                'amount': None,
                'market_cap': None,
                'pe_ratio': None,
                'pb_ratio': None,
            }
            
            # 1. 解析实时行情数据
            quote_match = re.search(r'var hq_str_[a-z]+[0-9]+="([^"]*)"', content)
            if quote_match:
                data_str = quote_match.group(1)
                if data_str:
                    fields = data_str.split(',')
                    if len(fields) >= 10:
                        # 0:股票名称, 1:开盘, 2:昨收, 3:现价, 4:最高, 5:最低, 8:成交量(手), 9:成交额(元)
                        try:
                            result['current_price'] = Decimal(fields[3]) if fields[3] else None
                            result['open_price'] = Decimal(fields[1]) if fields[1] else None
                            result['close_price'] = Decimal(fields[2]) if fields[2] else None
                            result['high_price'] = Decimal(fields[4]) if fields[4] else None
                            result['low_price'] = Decimal(fields[5]) if fields[5] else None
                            result['volume'] = Decimal(fields[8]) if fields[8] else None  # 手
                            result['amount'] = Decimal(fields[9]) if fields[9] else None  # 元
                        except Exception as e:
                            logger.warning(f"Error parsing quote fields: {e}")
            
            # 2. 解析指标数据（PE、PB等）
            # 格式：A,payh,每股收益,每股净资产,每股经营现金流,市净率,总股本,流通股本,总资产,净资产,营业收入...
            # 或者：A,market,每股收益,每股净资产,每股经营现金流,市盈率,市净率,总股本...
            indicator_match = re.search(r'var hq_str_[a-z]+[0-9]+_i="([^"]*)"', content)
            if indicator_match:
                data_str = indicator_match.group(1)
                if data_str:
                    fields = data_str.split(',')
                    if len(fields) >= 8:
                        try:
                            # 根据新浪接口的不同版本，PE和PB的位置可能不同
                            # 版本1: PE在位置5, PB在位置7
                            # 版本2: PE在位置21-22左右
                            
                            # 尝试从不同位置获取PE和PB
                            for i, field in enumerate(fields):
                                try:
                                    val = Decimal(field)
                                    # PE通常在5-50之间
                                    if 5 <= val <= 200 and not result['pe_ratio']:
                                        result['pe_ratio'] = val
                                    # PB通常在0.1-50之间
                                    if 0.1 <= val <= 50 and not result['pb_ratio'] and i > 4:
                                        result['pb_ratio'] = val
                                except:
                                    pass
                            
                            # 如果没有找到，尝试从固定位置获取
                            if not result['pe_ratio'] and len(fields) > 5:
                                try:
                                    val = Decimal(fields[5])
                                    if 5 <= val <= 200:
                                        result['pe_ratio'] = val
                                except:
                                    pass
                            
                            if not result['pb_ratio'] and len(fields) > 7:
                                try:
                                    val = Decimal(fields[7])
                                    if 0.1 <= val <= 50:
                                        result['pb_ratio'] = val
                                except:
                                    pass
                                    
                        except Exception as e:
                            logger.warning(f"Error parsing indicator fields: {e}")
            
            logger.info(f"Fetched comprehensive quote for {stock_code}: price={result['current_price']}, PE={result['pe_ratio']}, PB={result['pb_ratio']}")
            
            return result
                
        except Exception as e:
            logger.error(f"Error fetching real-time quote for {stock_code}: {e}")
            return None

    async def update_company_quotes(self, stock_code: str) -> bool:
        """
        更新公司行情信息 (实时)
        
        策略：优先使用 hq.sinajs.cn 接口（简单可靠），失败则回退到HTML页面解析。
        包含：当前价格、市值、市盈率、市净率、行业信息。
        """
        try:
            # 方法1: 使用新浪实时行情API（优先）
            quotes_data = await self._fetch_realtime_quote(stock_code)
            
            # 方法2: 如果API失败，尝试HTML页面解析（可以获取更多数据如PE、PB等）
            if not quotes_data or not quotes_data.get('current_price'):
                logger.warning(f"Real-time API failed for {stock_code}, trying HTML parsing...")
                
                # 1. Determine exchange prefix
                exchange_prefix = "sz" if stock_code.startswith(("0", "3")) else "sh"
                
                # URL 1: HTML Page
                url = f"https://finance.sina.com.cn/realstock/company/{exchange_prefix}{stock_code}/nc.shtml"
                
                headers = {
                    "Referer": "https://finance.sina.com.cn/",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                
                content = await self.fetch(url, headers=headers)
                
                # If HTML fetch fails
                if not content:
                    logger.warning(f"Failed to fetch quotes from HTML for {stock_code}")
                    return False
                    
                # 2. Parse Data
                quotes_data = self._parse_html_quotes(content, stock_code)
                
                if not quotes_data:
                    logger.warning(f"Failed to parse quotes data for {stock_code}")
                    return False
                    
            # 3. Update DB
            async with async_session_factory() as session:
                stmt = select(Company).where(Company.stock_code == stock_code)
                result = await session.execute(stmt)
                company = result.scalars().first()
                
                if not company:
                    logger.error(f"Company {stock_code} not found for update")
                    return False
                
                updated = False
                
                # Update basic quotes
                if quotes_data.get('current_price'):
                    company.current_price = quotes_data['current_price']
                    updated = True
                
                if quotes_data.get('pe_ratio'):
                    company.pe_ratio = quotes_data['pe_ratio']
                    updated = True
                    
                if quotes_data.get('pb_ratio'):
                    company.pb_ratio = quotes_data['pb_ratio']
                    updated = True
                    
                if quotes_data.get('market_cap'):
                    company.market_cap = quotes_data['market_cap']
                    updated = True
                
                # Update Industry
                industry_name = quotes_data.get('industry')
                if industry_name:
                    # Find or convert industry
                    stmt = select(Industry).where(Industry.name == industry_name)
                    result = await session.execute(stmt)
                    industry = result.scalars().first()
                    
                    if not industry:
                        # Create new industry
                        # Generate a simple code if possible, or use uuid/random? 
                        # Ideally assume industry codes are standard, but here we just have name.
                        # We can generate a code based on hash or just use auto-increment ID if code is not strict
                        import hashlib
                        code_hash = hashlib.md5(industry_name.encode('utf-8')).hexdigest()[:8].upper()
                        
                        industry = Industry(
                            code=f"IND_{code_hash}",
                            name=industry_name,
                            is_active=True
                        )
                        session.add(industry)
                        await session.flush() # flush to get ID
                        logger.info(f"Created new industry: {industry_name}")
                    
                    if company.industry_id != industry.id:
                        company.industry_id = industry.id
                        updated = True

                if updated:
                    await session.commit()
                    logger.info(f"Updated quotes for {stock_code}: Price={company.current_price}, PE={company.pe_ratio}, Industry={industry_name}")
                    return True
                else:
                    logger.info(f"No updates found for {stock_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating quotes for {stock_code}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _parse_html_quotes(self, html_content: str, stock_code: str) -> Optional[Dict[str, Any]]:
        """Parses HTML content for quote data (Price, PE, PB, MarketCap, Industry)"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            quotes_data = {
                'current_price': None,
                'market_cap': None,
                'pe_ratio': None,
                'pb_ratio': None,
                'industry': None
            }
            
            all_text = soup.get_text()
            
            # --- 1. Current Price ---
            # 新浪财经的实时价格通常在特定的元素中
            # 查找包含价格的元素
            price_found = False
            
            # 方法1: 查找包含价格的span或div元素
            price_elements = soup.find_all(['span', 'div'], string=re.compile(r'[\d.]+'))
            for el in price_elements:
                text = el.get_text(strip=True)
                # 检查是否是价格（通常格式为数字，可能有货币符号）
                # 排除明显不是价格的情况（如日期、年份等）
                if re.match(r'^\d+\.\d+$', text):
                    # 检查是否在合理的价格范围内（0.01 - 10000）
                    try:
                        price = Decimal(text)
                        if 0.01 <= price <= 10000:
                            # 检查上下文是否与股票相关
                            parent = el.parent
                            if parent:
                                parent_text = parent.get_text()
                                # 如果父元素包含"价格"、"现价"、"最新"等关键词
                                if any(keyword in parent_text for keyword in ['价格', '现价', '最新', 'Price', 'Last']):
                                    quotes_data['current_price'] = price
                                    price_found = True
                                    break
                    except:
                        pass
                if price_found:
                    break

            # --- 2. PE Ratio ---
            pe_patterns = [
                r'市盈率\(动态\)[：:\s]*(\d+\.?\d*)',
                r'市盈率[：:\s]*(\d+\.?\d*)',
                r'PE[：:\s]*(\d+\.?\d*)',
            ]
            for pattern in pe_patterns:
                match = re.search(pattern, all_text)
                if match:
                    try:
                        pe = Decimal(match.group(1))
                        if 0 < pe < 2000:
                            quotes_data['pe_ratio'] = pe
                            break
                    except:
                        pass

            # --- 3. PB Ratio ---
            pb_patterns = [
                r'市净率[：:\s]*(\d+\.?\d*)',
                r'PB[：:\s]*(\d+\.?\d*)',
            ]
            for pattern in pb_patterns:
                match = re.search(pattern, all_text)
                if match:
                    try:
                        pb = Decimal(match.group(1))
                        if 0 < pb < 200:
                            quotes_data['pb_ratio'] = pb
                            break
                    except:
                        pass
                        
            # --- 4. Market Cap ---
            # Handles units like 亿, 万
            mc_patterns = [
                r'市值[：:\s]*(\d+\.?\d*)\s*(亿|万|元)',
                r'总市值[：:\s]*(\d+\.?\d*)\s*(亿|万|元)',
            ]
            for pattern in mc_patterns:
                match = re.search(pattern, all_text)
                if match:
                    try:
                        val = Decimal(match.group(1))
                        unit = match.group(2)
                        
                        multiplier = 1
                        if unit == '亿':
                            multiplier = 10000 # Store in "Wan" (Ten Thousand) as per model comment "总市值(万元)"? 
                            # Model comment says: "总市值(万元)"
                            # '亿' = 10^8. '万' = 10^4.
                            # So 1 亿 = 10000 万. 
                        elif unit == '万':
                            multiplier = 1 
                        elif unit == '元':
                            multiplier = Decimal('0.0001')
                            
                        quotes_data['market_cap'] = val * multiplier
                        break
                    except:
                        pass

            # --- 5. Industry ---
            ind_patterns = [
                r'所属行业[：:\s]*([^,\n\r\t\s]+)',
                r'行业[：:\s]*([^,\n\r\t\s]+)',
                r'所属板块[：:\s]*([^,\n\r\t\s]+)',
            ]
            for pattern in ind_patterns:
                match = re.search(pattern, all_text)
                if match:
                    ind = match.group(1).strip()
                    # Filter out noise
                    if 1 < len(ind) < 20 and '净率' not in ind and '盈率' not in ind:
                         quotes_data['industry'] = ind
                         break
            
            # Debug logging
            logger.info(f"Parsed quotes for {stock_code}: {quotes_data}")
            return quotes_data

        except Exception as e:
            logger.warning(f"Error parsing HTML quotes for {stock_code}: {e}")
            return None

