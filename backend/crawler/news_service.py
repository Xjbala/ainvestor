# -*- coding: utf-8 -*-
"""
新闻舆情采集爬虫服务

从新浪财经等来源采集上市公司相关新闻，存储到 NewsSentiment 表。

数据源：sina（新浪财经）
"""

import asyncio
import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from sqlalchemy import select

from .base import CrawlerService
from ..persistence.financial_models import (
    CrawlerTask, CrawlerTaskStatus, NewsSentiment, Company
)

logger = logging.getLogger(__name__)

# 新浪财经滚动新闻 API（部分环境参数已失效，仅作兜底）
SINA_NEWS_SEARCH_URL = "https://feed.mix.sina.com.cn/api/roll/get"
# 新浪个股资讯页（稳定 HTML 源）
SINA_STOCK_NEWS_URL = (
    "https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{symbol}.phtml"
)
_NEWS_DATETIME_RE = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})(?:\s+(?P<time>\d{1,2}:\d{2}))?"
)

# 常见情绪关键词（用于简单情绪分析）
POSITIVE_KEYWORDS = [
    "增长", "盈利", "突破", "创新高", "利好", "上涨", "大涨", "翻倍",
    "业绩", "超预期", "强势", "龙头", "受益", "回暖", "复苏", "扩张",
]
NEGATIVE_KEYWORDS = [
    "亏损", "下跌", "暴跌", "跌停", "暴雷", "处罚", "调查", "退市",
    "违约", "风险", "下滑", "下滑", "缩水", "减持", "解禁", "诉讼",
    "立案", "违规", "造假", "爆仓", "危机", "困境", "破产",
]


class NewsCrawlerService(CrawlerService):
    """
    新闻舆情采集服务

    从新浪财经采集上市公司相关新闻，并进行简单的情绪分析。
    """

    def __init__(self, session, **kwargs):
        super().__init__(session, data_source_code="sina", **kwargs)
        # 新浪财经新闻搜索需要指定股票关键词
        self._news_sources = ["sina", "eastmoney", "guba"]

    async def crawl_company_list(self) -> List[Dict[str, Any]]:
        """新闻舆情采集不需要公司列表爬取，返回空列表"""
        return []

    async def crawl_financial_report(
        self,
        stock_code: str,
        report_type: str,
        year: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        爬取新闻情绪数据

        Args:
            stock_code: 股票代码
            report_type:  unused，保留以符合接口
            year: unused，保留以符合接口

        Returns:
            采集结果统计 {collected: int, failed: int}
        """
        return await self._collect_news(stock_code)

    async def _collect_news(self, stock_code: str) -> Dict[str, int]:
        """
        采集单个公司的新闻

        流程：
        1. 获取公司名称（用于新闻搜索）
        2. 从新浪财经抓取新闻列表
        3. 简单情绪分析
        4. 写入 NewsSentiment 表
        """
        result = {"collected": 0, "failed": 0}

        try:
            # 1. 获取公司名称
            stmt = select(Company).where(Company.stock_code == stock_code)
            company_result = await self.session.execute(stmt)
            company = company_result.scalar_one_or_none()

            if not company:
                logger.warning(f"[News] Company {stock_code} not found in DB")
                return result

            company_name = company.stock_name
            logger.info(f"[News] 开始采集 {stock_code} ({company_name})")

            # 2. 从新浪财经抓取新闻
            news_items = await self._fetch_sina_news(company_name, stock_code)

            if not news_items:
                logger.info(f"[News] {stock_code} 未获取到新闻")
                return result

            sample_titles = [n.get("title", "")[:30] for n in news_items[:3]]
            logger.info(
                f"[News] {stock_code} 抓取到 {len(news_items)} 条新闻, 示例={sample_titles}"
            )

            # 3. 去重：检查是否已存在相同标题
            existing_titles = await self._get_existing_titles(stock_code)

            # 4. 处理和存储
            for item in news_items:
                title = item.get("title", "").strip()
                if not title:
                    continue

                # 去重
                if title in existing_titles:
                    continue

                # 情绪分析
                sentiment = self._analyze_sentiment(title, item.get("summary", ""))

                # 写入数据库
                news_record = NewsSentiment(
                    company_code=stock_code,
                    source="sina",
                    title=title,
                    url=item.get("url", ""),
                    publish_date=item.get("publish_date", date.today()),
                    sentiment_score=sentiment["score"],
                    sentiment_label=sentiment["label"],
                    keywords=sentiment.get("keywords", []),
                )

                self.session.add(news_record)
                result["collected"] += 1

                # 每 20 条提交一次
                if result["collected"] % 20 == 0:
                    await self.session.commit()
                    existing_titles.add(title)

            # 最后提交剩余的
            if result["collected"] > 0:
                await self.session.commit()

            logger.info(f"[News] Collected {result['collected']} news items for {stock_code}")

        except Exception as e:
            logger.error(f"[News] Collection failed for {stock_code}: {e}", exc_info=True)
            await self.session.rollback()
            result["failed"] += 1

        return result

    async def _fetch_sina_news(
        self,
        company_name: str,
        stock_code: str,
        days: int = 90,
    ) -> List[Dict[str, Any]]:
        """
        从新浪财经抓取新闻。

        优先：个股资讯 HTML 页（稳定）
        兜底：滚动新闻 JSON 接口
        """
        cutoff_date = date.today() - timedelta(days=days)

        # 1) 个股资讯页
        html_items = await self._fetch_sina_stock_news_html(stock_code, cutoff_date)
        if html_items:
            logger.info(
                f"[News] HTML 源获取 {len(html_items)} 条 ({stock_code}/{company_name})"
            )
            return html_items

        # 2) JSON API 兜底
        logger.warning(f"[News] HTML 源为空，尝试 JSON API 兜底 ({stock_code})")
        return await self._fetch_sina_news_json(company_name, stock_code, cutoff_date)

    async def _fetch_sina_stock_news_html(
        self,
        stock_code: str,
        cutoff_date: date,
    ) -> List[Dict[str, Any]]:
        """解析新浪个股资讯页 .datelist 列表"""
        exchange_prefix = "sz" if stock_code.startswith(("0", "3")) else "sh"
        symbol = f"{exchange_prefix}{stock_code}"
        url = SINA_STOCK_NEWS_URL.format(symbol=symbol)
        news_items: List[Dict[str, Any]] = []

        try:
            html = await self.fetch(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://finance.sina.com.cn/",
                },
            )
            if not html:
                logger.warning(f"[News] 个股资讯页无响应: {url}")
                return news_items

            soup = BeautifulSoup(html, "html.parser")
            datelist = soup.select_one(".datelist") or soup.select_one("#con02-7")
            if not datelist:
                logger.warning(f"[News] 未找到 .datelist 节点: {symbol}")
                return news_items

            # 节点文本形如: 2026-07-24 15:22 标题链接
            # 逐 a 标签提取，并在邻近文本中找日期
            for a in datelist.find_all("a"):
                title = (a.get_text() or "").strip()
                href = (a.get("href") or "").strip()
                if not title or len(title) < 6:
                    continue
                if any(kw in title for kw in ["行情", "实时", "报价", "盘口", "自选股"]):
                    continue

                # 日期通常在 a 标签前的文本节点
                pub_date = date.today()
                prev = a.previous_sibling
                prev_text = ""
                if isinstance(prev, str):
                    prev_text = prev
                elif prev is not None:
                    prev_text = prev.get_text(" ", strip=True) if hasattr(prev, "get_text") else str(prev)
                # 再向上看父节点局部文本
                parent_text = a.parent.get_text(" ", strip=True) if a.parent else ""
                m = _NEWS_DATETIME_RE.search(prev_text) or _NEWS_DATETIME_RE.search(parent_text)
                if m:
                    try:
                        pub_date = datetime.strptime(m.group("date"), "%Y-%m-%d").date()
                    except ValueError:
                        pub_date = date.today()

                if pub_date < cutoff_date:
                    continue

                full_url = href
                if href and not href.startswith("http"):
                    full_url = urljoin("https://finance.sina.com.cn/", href)

                news_items.append({
                    "title": title,
                    "summary": "",
                    "url": full_url,
                    "publish_date": pub_date,
                    "media": "sina",
                })

            # 去重（同标题）
            dedup = {}
            for item in news_items:
                dedup[item["title"]] = item
            news_items = list(dedup.values())
            news_items.sort(key=lambda x: x["publish_date"], reverse=True)
            logger.info(
                f"[News] 解析个股资讯页 {symbol}: {len(news_items)} 条 "
                f"(cutoff={cutoff_date})"
            )
        except Exception as e:
            logger.error(f"[News] 解析个股资讯页失败 {stock_code}: {e}", exc_info=True)

        return news_items

    async def _fetch_sina_news_json(
        self,
        company_name: str,
        stock_code: str,
        cutoff_date: date,
    ) -> List[Dict[str, Any]]:
        """滚动新闻 JSON 接口兜底（接口参数可能失效）"""
        news_items: List[Dict[str, Any]] = []
        params = {
            "pageid": "153",
            "lid": "2516",
            "kw": company_name,
            "num": 50,
            "page": "1",
            "r": 0.1,
        }

        try:
            data = await self.fetch_json(SINA_NEWS_SEARCH_URL, params=params)
            if not data:
                return news_items

            result = data.get("result") or {}
            status = result.get("status") or {}
            if status.get("code") not in (0, "0", None):
                logger.warning(
                    f"[News] JSON API 返回异常 code={status.get('code')} "
                    f"msg={status.get('msg')} stock={stock_code}"
                )

            entries = result.get("data", []) or []
            if isinstance(entries, dict):
                entries = entries.get("list") or entries.get("data") or []

            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                title = (entry.get("title") or "").strip()
                if not title:
                    continue

                ctime = entry.get("ctime") or entry.get("time") or ""
                try:
                    pub_date = datetime.strptime(str(ctime)[:19], "%Y-%m-%d %H:%M:%S").date()
                except (ValueError, TypeError):
                    try:
                        pub_date = datetime.strptime(str(ctime)[:10], "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        pub_date = date.today()

                if pub_date < cutoff_date:
                    continue
                if any(kw in title for kw in ["行情", "实时", "报价", "盘口"]):
                    continue

                news_items.append({
                    "title": title,
                    "summary": entry.get("intro", entry.get("summary", "")),
                    "url": entry.get("url", ""),
                    "publish_date": pub_date,
                    "media": "sina",
                })

            logger.info(f"[News] JSON API 获取 {len(news_items)} 条 ({stock_code})")
        except Exception as e:
            logger.error(f"[News] JSON API 失败 {stock_code}: {e}")

        return news_items

    async def _get_existing_titles(self, stock_code: str) -> set:
        """获取已存储的新闻标题集合，用于去重"""
        stmt = select(NewsSentiment.title).where(
            NewsSentiment.company_code == stock_code
        )
        result = await self.session.execute(stmt)
        return set(row[0] for row in result.all())

    def _analyze_sentiment(
        self,
        title: str,
        summary: str,
    ) -> Dict[str, Any]:
        """
        简单情绪分析

        基于关键词匹配判断新闻情绪。
        正面关键词加分，负面关键词减分。

        Returns:
            {"score": float, "label": str, "keywords": list}
        """
        text = title + " " + summary
        score = 0.0
        matched_keywords = []

        for kw in POSITIVE_KEYWORDS:
            if kw in text:
                score += 0.2
                matched_keywords.append(kw)

        for kw in NEGATIVE_KEYWORDS:
            if kw in text:
                score -= 0.2
                matched_keywords.append(kw)

        # 归一化到 [-1, 1]
        score = max(-1.0, min(1.0, score))

        # 确定情绪标签
        if score > 0.1:
            label = "positive"
        elif score < -0.1:
            label = "negative"
        else:
            label = "neutral"

        return {
            "score": round(score, 3),
            "label": label,
            "keywords": matched_keywords[:10],
        }
