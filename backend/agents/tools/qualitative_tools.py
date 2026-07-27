# -*- coding: utf-8 -*-
"""
定性分析工具函数

为 Agent 提供定性数据的读取接口。
这些数据来自爬虫采集的年报 MD&A、新闻舆情、行业竞争分析等。
每个工具函数内部自行管理数据库 session 生命周期。
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

from backend.persistence.db import async_session_factory
from backend.persistence.financial_models import QualitativeReport, NewsSentiment

logger = logging.getLogger(__name__)


async def get_qualitative_insights(
    stock_code: str,
    years: int = 3,
) -> ToolResponse:
    """
    获取公司的定性分析洞察

    从已采集的年报/季报 MD&A 数据中提取结构化信息，包括：
    - 核心竞争力分析
    - 风险因素
    - 管理层未来展望
    - 产能规划

    Args:
        stock_code: 股票代码
        years: 最近 N 年的数据

    Returns:
        结构化定性分析结果
    """
    try:
        async with async_session_factory() as session:
            from sqlalchemy import select, desc

            stmt = select(QualitativeReport).where(
                QualitativeReport.company_code == stock_code,
            ).order_by(
                desc(QualitativeReport.report_period)
            ).limit(years)

            result = await session.execute(stmt)
            reports = result.scalars().all()

            if not reports:
                return ToolResponse(content=[TextBlock(
                    type="text",
                    text=json.dumps({
                        "status": "no_data",
                        "message": f"未找到 {stock_code} 的定性数据。请先通过数据管理页面采集年报/季报。",
                    }, ensure_ascii=False, indent=2)
                )])

            insights = []
            for report in reports:
                insight = {
                    "report_period": str(report.report_period),
                    "report_type": report.report_type,
                    "publish_date": str(report.publish_date) if report.publish_date else None,
                    "core_competencies": report.core_competencies,
                    "risk_factors": report.risk_factors,
                    "risk_keywords": report.risk_keywords or [],
                    "future_outlook": report.future_outlook,
                    "capacity_plans": report.capacity_plans,
                    "overview": report.overview,
                }
                insights.append(insight)

            response = {
                "status": "ok",
                "stock_code": stock_code,
                "years_covered": len(insights),
                "insights": insights,
            }

            return ToolResponse(content=[TextBlock(
                type="text",
                text=json.dumps(response, ensure_ascii=False, indent=2)
            )])

    except Exception as e:
        logger.error(f"get_qualitative_insights failed for {stock_code}: {e}")
        error_text = json.dumps({
            "status": "error",
            "message": f"获取定性数据失败: {str(e)}"
        }, ensure_ascii=False)
        return ToolResponse(content=[TextBlock(type="text", text=error_text)])


async def get_industry_competition(
    stock_code: str,
) -> ToolResponse:
    """
    获取公司所在行业的竞争格局分析

    基于已有财务数据计算：
    - CR3/CR5 集中度指标
    - HHI 指数
    - 毛利率离散度（价格竞争信号）
    - 行业增速趋势
    - 竞争程度判断
    - 周期阶段判断

    Args:
        stock_code: 股票代码

    Returns:
        行业竞争分析结果
    """
    try:
        async with async_session_factory() as session:
            from sqlalchemy import select
            from ..persistence.financial_models import Company

            # 获取公司行业信息
            stmt = select(Company).where(Company.stock_code == stock_code)
            company = (await session.execute(stmt)).scalar_one_or_none()

            if not company:
                return ToolResponse(content=[TextBlock(
                    type="text",
                    text=json.dumps({
                        "status": "error",
                        "message": f"未找到公司 {stock_code}"
                    }, ensure_ascii=False)
                )])

            if not company.industry_id:
                return ToolResponse(content=[TextBlock(
                    type="text",
                    text=json.dumps({
                        "status": "no_industry",
                        "message": f"{stock_code} 尚未分配行业信息"
                    }, ensure_ascii=False)
                )])

            # 调用行业竞争分析服务
            from backend.analysis.industry_competition import IndustryCompetitionService
            service = IndustryCompetitionService()
            result = await service.analyze_industry(
                session, company.industry_id
            )

            return ToolResponse(content=[TextBlock(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2, default=str)
            )])

    except Exception as e:
        logger.error(f"get_industry_competition failed for {stock_code}: {e}")
        error_text = json.dumps({
            "status": "error",
            "message": f"获取行业竞争数据失败: {str(e)}"
        }, ensure_ascii=False)
        return ToolResponse(content=[TextBlock(type="text", text=error_text)])


async def get_news_sentiment(
    stock_code: str,
    days: int = 90,
) -> ToolResponse:
    """
    获取公司新闻情绪分析

    从已采集的新闻数据中统计：
    - 正面/负面/中性新闻数量
    - 情绪得分趋势
    - 关键主题词

    Args:
        stock_code: 股票代码
        days: 最近 N 天的数据

    Returns:
        情绪分析结果
    """
    try:
        async with async_session_factory() as session:
            from sqlalchemy import select, func, and_
            from datetime import timedelta

            cutoff_date = (datetime.now() - timedelta(days=days)).date()

            stmt = select(NewsSentiment).where(
                and_(
                    NewsSentiment.company_code == stock_code,
                    NewsSentiment.publish_date >= cutoff_date,
                )
            ).order_by(
                desc(NewsSentiment.publish_date)
            )

            result = await session.execute(stmt)
            news_items = result.scalars().all()

            if not news_items:
                return ToolResponse(content=[TextBlock(
                    type="text",
                    text=json.dumps({
                        "status": "no_data",
                        "message": f"未找到 {stock_code} 最近 {days} 天的新闻情绪数据。请先通过数据管理页面采集新闻。",
                    }, ensure_ascii=False)
                )])

            # 统计
            positive_count = sum(1 for n in news_items if n.sentiment_label == "positive")
            negative_count = sum(1 for n in news_items if n.sentiment_label == "negative")
            neutral_count = sum(1 for n in news_items if n.sentiment_label == "neutral")
            avg_score = sum(n.sentiment_score for n in news_items) / len(news_items)

            # 提取关键词
            all_keywords = []
            for n in news_items:
                if n.keywords:
                    all_keywords.extend(n.keywords)

            keyword_freq = {}
            for kw in all_keywords:
                keyword_freq[kw] = keyword_freq.get(kw, 0) + 1
            top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:10]

            response = {
                "status": "ok",
                "stock_code": stock_code,
                "period_days": days,
                "total_news": len(news_items),
                "sentiment_breakdown": {
                    "positive": positive_count,
                    "negative": negative_count,
                    "neutral": neutral_count,
                },
                "avg_sentiment_score": round(avg_score, 3),
                "top_keywords": [{"keyword": k, "count": c} for k, c in top_keywords],
            }

            return ToolResponse(content=[TextBlock(
                type="text",
                text=json.dumps(response, ensure_ascii=False, indent=2)
            )])

    except Exception as e:
        logger.error(f"get_news_sentiment failed for {stock_code}: {e}")
        error_text = json.dumps({
            "status": "error",
            "message": f"获取新闻情绪数据失败: {str(e)}"
        }, ensure_ascii=False)
        return ToolResponse(content=[TextBlock(type="text", text=error_text)])
