# -*- coding: utf-8 -*-
"""
定性数据采集爬虫服务

从巨潮资讯网(cninfo.com.cn)下载上市公司年报/季报PDF，
通过 MinerU 解析为 Markdown，再由 MDPAExtractor 提取结构化 MD&A 数据。

数据源：cninfo（巨潮资讯网）
"""

import asyncio
import logging
import os
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from .base import CrawlerService
from .qualitative.cninfo_crawler import CninfoCrawler
from .qualitative.mineru_client import MinerUClient
from .qualitative.mdpa_extractor import MDAExtractor
from ..persistence.financial_models import (
    CrawlerTask, CrawlerTaskStatus, QualitativeReport, Company
)

logger = logging.getLogger(__name__)

# MinerU API Key（可选，用于 Precision API 降级）
MINERU_API_KEY = os.getenv("MINERU_API_KEY")


class QualitativeCrawlerService(CrawlerService):
    """
    定性数据采集服务

    流程：
    1. CninfoCrawler 搜索公司公告，筛选年报/季报PDF
    2. 下载PDF → MinerU 解析为 Markdown
    3. MDPAExtractor 提取结构化 MD&A 字段
    4. 写入 QualitativeReport 表
    """

    def __init__(self, session, **kwargs):
        super().__init__(session, data_source_code="cninfo", **kwargs)
        self._cninfo = CninfoCrawler(timeout=self.timeout)
        self._mineru = MinerUClient(api_key=MINERU_API_KEY)
        self._extractor = MDAExtractor()

    async def __aenter__(self):
        # 父类已处理 HTTP 客户端，这里不需要额外操作
        await super().__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await super().__aexit__(exc_type, exc_val, exc_tb)
        await self._cninfo.close()
        await self._mineru.close()

    async def crawl_company_list(self) -> List[Dict[str, Any]]:
        """定性数据采集不需要公司列表爬取，返回空列表"""
        return []

    async def crawl_financial_report(
        self,
        stock_code: str,
        report_type: str,
        year: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        爬取定性报告数据

        Args:
            stock_code: 股票代码
            report_type: 报告类型 (annual/semi/q1/q3/all)
            year: 年份（可选，不提供则采集所有年份）

        Returns:
            采集结果统计 {collected: int, failed: int}
        """
        return await self._collect_qualitative_reports(stock_code, report_type, year)

    async def _collect_qualitative_reports(
        self,
        stock_code: str,
        report_type: str,
        year: Optional[int] = None,
    ) -> Dict[str, int]:
        """
        采集单个公司的定性报告

        流程：搜索公告 → 下载PDF → MinerU解析 → MD&A提取 → 入库
        """
        result = {"collected": 0, "failed": 0}

        try:
            # 1. 搜索公告
            logger.info(
                f"[Qualitative] 搜索公告 {stock_code} type={report_type} year={year or 'all'}"
            )
            announcements = await self._cninfo.search_announcements(
                stock_code=stock_code,
                year=year,
                report_type=report_type,
            )

            if not announcements:
                logger.info(f"[Qualitative] 未找到公告 {stock_code} type={report_type} year={year}")
                return result

            titles_preview = [a.get("title", "")[:40] for a in announcements[:5]]
            logger.info(
                f"[Qualitative] {stock_code} 找到 {len(announcements)} 份公告, "
                f"示例={titles_preview}"
            )

            # 2. 逐个处理公告（单份失败不影响后续，且必须 rollback 以免污染 Session）
            for ann in announcements:
                try:
                    pdf_url = ann.get("pdf_url")
                    if not pdf_url:
                        logger.warning(f"[Qualitative] No PDF URL for announcement: {ann.get('title')}")
                        result["failed"] += 1
                        continue

                    # 3. MinerU 解析为 Markdown
                    # 优先：远程 URL 直传 extract/task（巨潮 PDF 公网可访问）
                    # 回退：本地下载后 file-urls/batch 上传（body 须为 {"files":[{"name":...}]}）
                    logger.info(f"[Qualitative] Parsing PDF via MinerU URL: {pdf_url}")
                    parse_result = await self._mineru.parse_by_url(pdf_url, use_precision=True)

                    if parse_result.get("status") != "success":
                        logger.warning(
                            f"[Qualitative] MinerU URL parse failed: {parse_result.get('error')}; "
                            f"fallback to local upload"
                        )
                        pdf_bytes = await self._cninfo.download_pdf(pdf_url)
                        if not pdf_bytes:
                            logger.warning(f"[Qualitative] Failed to download PDF for: {ann.get('title')}")
                            result["failed"] += 1
                            continue
                        parse_result = await self._mineru.parse_local_file(
                            pdf_bytes,
                            filename=f"{stock_code}_{ann.get('ann_id', 'report')}.pdf",
                        )
                        if parse_result.get("status") != "success":
                            logger.warning(
                                f"[Qualitative] MinerU local parse failed: {parse_result.get('error')}"
                            )
                            result["failed"] += 1
                            continue

                    markdown = parse_result.get("markdown", "")
                    if not markdown or len(markdown) < 100:
                        logger.warning(f"[Qualitative] Empty or too-short markdown for: {ann.get('title')}")
                        result["failed"] += 1
                        continue

                    # 5. MD&A 结构化提取
                    extracted = self._extractor.extract(markdown)
                    risk_keywords = self._extractor.extract_risk_keywords(extracted.get("risk_factors"))

                    # 6. 写入数据库
                    report_period = await self._save_qualitative_report(
                        stock_code=stock_code,
                        announcement=ann,
                        markdown=markdown,
                        extracted=extracted,
                        risk_keywords=risk_keywords,
                    )

                    # 7. 分部抽取钩子（年报优先；失败不影响主流程）
                    if report_period is not None:
                        try:
                            seg_count = await self._extract_and_save_segments(
                                stock_code=stock_code,
                                markdown=markdown,
                                report_period=report_period,
                                report_type=ann.get("report_type", "annual"),
                                source_url=ann.get("pdf_url", ""),
                            )
                            result.setdefault("segments_extracted", 0)
                            result["segments_extracted"] = result.get("segments_extracted", 0) + seg_count
                        except Exception as se:
                            logger.warning(f"[Qualitative] Segment extract hook failed: {se}")

                    result["collected"] += 1
                    logger.info(f"[Qualitative] Saved report: {ann.get('title')}")

                except Exception as item_err:
                    result["failed"] += 1
                    logger.error(
                        f"[Qualitative] Failed item {stock_code} "
                        f"{ann.get('title')}: {item_err}",
                        exc_info=True,
                    )
                    try:
                        await self.session.rollback()
                    except Exception:
                        pass

                # 礼貌延迟
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"[Qualitative] Collection failed for {stock_code}: {e}", exc_info=True)
            result["failed"] += 1
            try:
                await self.session.rollback()
            except Exception:
                pass

        return result

    async def _save_qualitative_report(
        self,
        stock_code: str,
        announcement: dict,
        markdown: str,
        extracted: Dict[str, Optional[str]],
        risk_keywords: List[str],
    ) -> Optional[date]:
        """
        将定性报告数据保存到数据库。
        返回 report_period（已存在时也返回，便于分部钩子复用 Markdown）。
        """
        from sqlalchemy.exc import IntegrityError

        # 解析披露日期
        ann_time = announcement.get("ann_time", "")
        try:
            publish_date = date.fromisoformat(ann_time[:10]) if ann_time else date.today()
        except (ValueError, TypeError):
            publish_date = date.today()

        # 解析报告期间（从标题推断）
        report_period = self._infer_report_period(announcement)

        # 检查是否已存在（去重）
        stmt = select(QualitativeReport).where(
            QualitativeReport.company_code == stock_code,
            QualitativeReport.report_period == report_period,
            QualitativeReport.report_type == announcement.get("report_type", "unknown"),
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"[Qualitative] Report already exists for {stock_code} on {report_period}, skipping")
            # 若旧记录无全文而本次有，补写 management_discussion
            if not existing.management_discussion and markdown:
                existing.management_discussion = markdown
                existing.raw_markdown_length = len(markdown)
                try:
                    await self.session.commit()
                except Exception:
                    await self.session.rollback()
            return report_period

        report = QualitativeReport(
            company_code=stock_code,
            report_type=announcement.get("report_type", "unknown"),
            report_period=report_period,
            publish_date=publish_date,
            overview=extracted.get("overview"),
            revenue_analysis=extracted.get("revenue_analysis"),
            cost_analysis=extracted.get("cost_analysis"),
            rd_investment=extracted.get("rd_investment"),
            core_competencies=extracted.get("core_competencies"),
            risk_factors=extracted.get("risk_factors"),
            risk_keywords=risk_keywords,
            future_outlook=extracted.get("future_outlook"),
            capacity_plans=extracted.get("capacity_plans"),
            management_discussion=markdown,  # 完整 Markdown 作为原始文本
            source_url=announcement.get("pdf_url", ""),
            raw_markdown_length=len(markdown),
            extraction_method="mineru",
        )

        self.session.add(report)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            logger.info(f"[Qualitative] Duplicate key for {stock_code} on {report_period}, skipping")
            return report_period
        except Exception as e:
            await self.session.rollback()
            logger.error(
                f"[Qualitative] Failed to save report for {stock_code} "
                f"{report_period}/{announcement.get('report_type')}: {e}"
            )
            raise
        return report_period

    async def _extract_and_save_segments(
        self,
        stock_code: str,
        markdown: str,
        report_period: date,
        report_type: str = "annual",
        source_url: str = "",
    ) -> int:
        """从 Markdown 抽取分部并写入 company_segments。"""
        # 年报优先；中报也可；季报通常分部不全，仍尝试
        from .qualitative.segment_extractor import SegmentExtractor
        from ..persistence.segment_repository import SegmentRepository

        extractor = SegmentExtractor()
        use_llm = os.getenv("SEGMENT_LLM_FALLBACK", "true").lower() in ("1", "true", "yes")
        extracted = extractor.extract(
            markdown,
            company_code=stock_code,
            report_period=report_period,
            use_llm_fallback=use_llm,
        )
        segs = extracted.get("segments") or []
        if len(segs) < 2:
            logger.info(
                f"[Qualitative] No usable segments for {stock_code} "
                f"({extracted.get('count', 0)} found, method={extracted.get('method')})"
            )
            return 0

        repo = SegmentRepository(self.session)
        rows = await repo.replace_period_segments(
            stock_code,
            report_period,
            segs,
            report_type=report_type or "annual",
            source=extracted.get("source") or "cninfo_pdf",
            source_url=source_url or None,
            confidence=extracted.get("confidence") or "medium",
        )
        logger.info(f"[Qualitative] Saved {len(rows)} segments for {stock_code} @ {report_period}")
        return len(rows)

    @staticmethod
    def _infer_report_period(announcement: dict) -> date:
        """
        从公告信息推断报告期间

        优先从标题提取报告年份（如「2025年年度报告」），
        因为年报通常在次年披露，不能直接用 ann_time 的年份。
        回退：披露日在 1-4 月且为年报时，按上年；其余按披露年。
        """
        import re

        ann_time = announcement.get("ann_time", "")
        report_type = announcement.get("report_type", "unknown")
        title = announcement.get("title") or ""

        try:
            pub_date = date.fromisoformat(ann_time[:10]) if ann_time else date.today()

            year = None
            # 标题优先：2025年年度报告 / 2025年半年度报告 / 2025年第三季度报告
            m = re.search(r"(20\d{2})\s*年", title)
            if m:
                year = int(m.group(1))
            else:
                year = pub_date.year
                # 年报常见次年披露：披露日在 1-6 月则回退一年
                if report_type == "annual" and pub_date.month <= 6:
                    year = pub_date.year - 1

            if report_type == "annual":
                return date(year, 12, 31)
            elif report_type == "semi":
                return date(year, 6, 30)
            elif report_type == "q1":
                return date(year, 3, 31)
            elif report_type == "q3":
                return date(year, 9, 30)
            else:
                return pub_date
        except (ValueError, TypeError):
            return date.today()
