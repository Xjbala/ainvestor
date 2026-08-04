# -*- coding: utf-8 -*-
"""
爬虫任务执行引擎

负责调度和运行后台爬虫任务。
支持单公司逐表采集和全量公司批量采集两种模式。
"""

import asyncio
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import CrawlerService, append_task_log, merge_task_log
from .sina_crawler import SinaCrawlerService
from .exchange_crawler import ExchangeCrawler
from .qualitative_service import QualitativeCrawlerService
from .news_service import NewsCrawlerService
from ..analysis.financial_validation import (
    is_year_complete_for_resume,
    required_core_codes,
    validation_profile_for_industry,
)
from ..persistence.db import async_session_factory
from ..persistence.financial_models import (
    CrawlerTask, CrawlerTaskStatus, CrawlerDataType, DataSource, Company,
    FinancialData, ReportType, CompanyStatus, Industry,
)

logger = logging.getLogger(__name__)

# 全量采集默认参数
DEFAULT_YEARS = 5  # 默认采集最近5年
MAX_CONCURRENT = 10  # 最大并发公司数
PER_COMPANY_DELAY = 0.5  # 每家公司的请求间隔(秒)，避免被限流


class CrawlerEngine:
    """
    爬虫引擎

    调度各类爬虫服务，处理后台任务生命周期。
    支持两种采集模式：
    1. 单公司逐表模式：指定公司列表，逐张表采集
    2. 全量批量模式：自动获取全量公司，并发采集三大报表
    """

    def __init__(self):
        self._service_cache: Dict[str, Any] = {}

    async def execute_task(self, task_id: str):
        """
        异步执行一个爬虫任务

        Args:
            task_id: 数据库中 CrawlerTask 的 ID
        """
        async with async_session_factory() as session:
            # 1. 获取任务详情
            stmt = select(CrawlerTask).where(CrawlerTask.id == task_id)
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()

            if not task:
                logger.error(f"CrawlerEngine: Task {task_id} not found")
                return

            # 如果任务不再是 pending，说明已被其他进程或逻辑处理
            if task.status != CrawlerTaskStatus.PENDING:
                logger.warning(f"CrawlerEngine: Task {task_id} is in status {task.status}, skipping")
                return

            # 2. 准备对应的爬虫服务
            ds_stmt = select(DataSource).where(DataSource.id == task.data_source_id)
            ds_res = await session.execute(ds_stmt)
            data_source = ds_res.scalar_one_or_none()

            if not data_source:
                logger.error(f"CrawlerEngine: Data source for task {task_id} not found")
                await self._fail_task(session, task, "Data source not found")
                return

            # 3. 创建服务实例
            service = self._create_service(session, data_source.code)
            if not service:
                logger.error(f"CrawlerEngine: Unsupported data source {data_source.code}")
                await self._fail_task(session, task, f"Unsupported data source {data_source.code}")
                return

            # 4. 执行任务
            try:
                async with service:
                    logger.info(f"CrawlerEngine: Starting task {task.task_name} (ID: {task_id})")
                    await service.start_task(task)
                    await append_task_log(
                        session,
                        task,
                        f"调度开始 | 数据源={data_source.code}({data_source.name}) | 数据类型={task.data_type.value}",
                    )

                    if task.data_type == CrawlerDataType.COMPANY_LIST:
                        await append_task_log(session, task, "进入公司列表采集流程")
                        if data_source.code == "exchange_api":
                            await append_task_log(session, task, "使用交易所官方 API 同步公司列表")
                            companies = await service.sync_companies_from_exchanges()
                            count = len(companies or [])
                            task.total_count = count
                            task.success_count = count
                            await append_task_log(session, task, f"交易所同步完成，共 {count} 家公司")
                        else:
                            await append_task_log(session, task, "使用新浪财经抓取公司列表")
                            companies = await service.crawl_company_list()
                            await service.save_companies(companies)
                            count = len(companies or [])
                            task.total_count = count
                            task.success_count = count
                            await append_task_log(session, task, f"公司列表采集完成，共 {count} 家公司")
                        await service.complete_task(task)

                    elif task.data_type == CrawlerDataType.BATCH_FINANCIAL_DATA:
                        # 全量批量采集模式
                        await self._execute_batch_financial_collection(service, task, session)

                    elif task.data_type in [CrawlerDataType.BALANCE_SHEET, CrawlerDataType.INCOME_STATEMENT, CrawlerDataType.CASH_FLOW]:
                        # 单公司逐表采集模式
                        await self._execute_single_report_collection(service, task, session)

                    elif task.data_type == CrawlerDataType.QUALITATIVE_REPORT:
                        # 定性数据采集模式
                        await self._execute_qualitative_collection(service, task, session)

                    elif task.data_type == CrawlerDataType.NEWS_SENTIMENT:
                        # 新闻舆情采集模式
                        await self._execute_news_collection(service, task, session)

                    else:
                        logger.warning(f"CrawlerEngine: Unsupported data type {task.data_type}")
                        await self._fail_task(session, task, f"Unsupported data type {task.data_type}")

            except Exception as e:
                logger.error(f"CrawlerEngine: Task {task_id} failed with error: {e}", exc_info=True)
                await self._fail_task(session, task, str(e))

    async def _execute_batch_financial_collection(
        self,
        service: CrawlerService,
        task: CrawlerTask,
        session: AsyncSession,
    ):
        """
        全量批量采集财务报表

        流程：
        1. 从数据库获取所有活跃公司列表
        2. 确定采集年份范围（默认最近 N 年）
        3. 并发采集三大报表，带限速和断点续采
        """
        # 1. 获取目标公司列表
        target_codes = task.target_companies or []
        if not target_codes:
            # 自动获取所有活跃公司
            await append_task_log(session, task, "未指定目标公司，从数据库加载全部活跃公司")
            logger.info("No target companies specified, fetching all active companies...")
            stmt = select(Company.stock_code).where(Company.status == CompanyStatus.ACTIVE)
            result = await session.execute(stmt)
            target_codes = [row[0] for row in result.all()]

        total_companies = len(target_codes)
        logger.info(f"Batch financial collection: {total_companies} companies to process")
        await append_task_log(
            session,
            task,
            f"批量财务采集启动 | 公司数={total_companies} | 并发上限={MAX_CONCURRENT}",
        )

        if total_companies == 0:
            await append_task_log(session, task, "无可用公司，任务失败", level="ERROR")
            await service.complete_task(task, success=False)
            return

        # 2. 确定采集年份范围
        years = []
        if task.extra_params and isinstance(task.extra_params, dict):
            years = [str(y) for y in (task.extra_params.get("years", []) or [])]
        if not years or not all(y.isdigit() and len(y) == 4 for y in years):
            # 默认最近5年
            end_year = date.today().year - 1  # 不包含当年
            years = [str(y) for y in range(end_year - DEFAULT_YEARS + 1, end_year + 1)]
        year_ints = [int(y) for y in years]
        logger.info(f"Year range: {years}")
        await append_task_log(session, task, f"目标年份: {', '.join(years)}")

        # 3. 定义报表类型
        report_configs = [
            ("BS", ReportType.BS, "资产负债表"),
            ("IS", ReportType.IS, "利润表"),
            ("CF", ReportType.CF, "现金流量表"),
        ]

        # 4. 统计已有数据，实现断点续采
        logger.info("Checking existing data for resume capability...")
        await append_task_log(session, task, "扫描已有财务数据，计算缺失任务（断点续采）")
        missing = await self._find_missing_data(session, target_codes, report_configs, year_ints)
        total_jobs = sum(len(codes) for codes in missing.values())
        missing_summary = (
            f"缺失任务={total_jobs} | BS={len(missing.get('BS', []))} "
            f"IS={len(missing.get('IS', []))} CF={len(missing.get('CF', []))}"
        )
        logger.info(f"Missing data jobs: {total_jobs} (BS: {len(missing.get('BS', []))}, IS: {len(missing.get('IS', []))}, CF: {len(missing.get('CF', []))})")
        await append_task_log(session, task, missing_summary)

        if total_jobs == 0:
            logger.info("All data already exists, marking task as completed")
            await append_task_log(session, task, "目标范围内数据已齐全，无需采集")
            task.total_count = 0
            task.success_count = 0
            task.error_count = 0
            await service.complete_task(task, success=True)
            return

        # 5. 并发采集
        success_count = 0
        error_count = 0
        empty_count = 0
        sem = asyncio.Semaphore(MAX_CONCURRENT)  # 并发信号量
        collected = 0
        log_lock = asyncio.Lock()
        error_samples: List[str] = []

        async def _collect_one(stock_code: str, report_type_str: str, report_type_enum: ReportType, report_name: str):
            nonlocal success_count, error_count, empty_count, collected
            async with sem:
                try:
                    data_list = await service.crawl_financial_report(stock_code, report_type_str)
                    if data_list:
                        # 过滤出目标年份的数据
                        filtered = [d for d in data_list if d.get("report_date", "")[:4] in years]
                        if filtered:
                            save_summary = await service.save_to_db(
                                filtered, crawl_task_id=task.id
                            )
                            safe_rows = (
                                save_summary["inserted_rows"]
                                + save_summary["updated_rows"]
                            )
                            collected += 1
                            if safe_rows:
                                success_count += 1
                            else:
                                error_count += 1
                                error_samples.append(
                                    f"{stock_code} {report_name}: 无安全科目匹配"
                                )
                            quality_detail = (
                                f"安全写入={safe_rows} 未匹配={save_summary['unmatched_rows']} "
                                f"歧义={save_summary['ambiguous_rows']} "
                                f"拒绝={save_summary['rejected_rows']} "
                                f"冲突={save_summary['conflict_rows']}"
                            )
                            if collected % 20 == 0 or collected == total_jobs:
                                async with log_lock:
                                    task.success_count = success_count
                                    task.error_count = error_count
                                    task.total_count = total_jobs
                                    task.progress = float((success_count + error_count + empty_count) / max(total_jobs, 1) * 100)
                                    await append_task_log(
                                        session,
                                        task,
                                        f"批量进度 {collected}/{total_jobs} | 最近{'成功' if safe_rows else '失败'}: "
                                        f"{stock_code} {report_name} | {quality_detail}",
                                        level="INFO" if safe_rows else "WARNING",
                                    )
                                    logger.info(
                                        "Batch progress: %s/%s %s %s | %s",
                                        collected,
                                        total_jobs,
                                        stock_code,
                                        report_name,
                                        quality_detail,
                                    )
                        else:
                            # 有返回但目标年份无数据
                            empty_count += 1
                            collected += 1
                    else:
                        # 该公司该报表无数据，不算错误
                        empty_count += 1
                        collected += 1
                except Exception as e:
                    error_count += 1
                    collected += 1
                    err_msg = f"{stock_code} {report_name}: {e}"
                    logger.error(f"Error collecting {report_name} for {stock_code}: {e}")
                    async with log_lock:
                        if len(error_samples) < 30:
                            error_samples.append(err_msg)
                            await append_task_log(session, task, f"采集失败: {err_msg}", level="ERROR")

        # 按报表类型分组执行，便于追踪
        for rt_str, rt_enum, rt_name in report_configs:
            codes_to_collect = missing.get(rt_str, [])
            if not codes_to_collect:
                logger.info(f"{rt_name}: all data already exists, skipping")
                await append_task_log(session, task, f"{rt_name}: 数据已齐全，跳过")
                continue

            logger.info(f"{rt_name}: collecting {len(codes_to_collect)} companies...")
            await append_task_log(
                session,
                task,
                f"开始采集{rt_name} | 公司数={len(codes_to_collect)} | 示例={','.join(codes_to_collect[:5])}",
            )
            tasks = [
                _collect_one(code, rt_str, rt_enum, rt_name)
                for code in codes_to_collect
            ]
            await asyncio.gather(*tasks)
            await append_task_log(
                session,
                task,
                f"{rt_name}采集阶段完成 | 累计成功={success_count} 失败={error_count} 空数据={empty_count}",
            )

            # 报表间稍作停顿
            await asyncio.sleep(1)

        # 6. 更新任务进度
        task.total_count = total_jobs
        task.success_count = success_count
        task.error_count = error_count
        task.progress = float((success_count + error_count + empty_count) / max(total_jobs, 1) * 100)
        task.completed_at = datetime.utcnow()

        if error_count == 0:
            task.status = CrawlerTaskStatus.SUCCESS
        else:
            task.status = CrawlerTaskStatus.SUCCESS if success_count > 0 else CrawlerTaskStatus.FAILED

        summary = (
            f"批量财务采集结束 | 成功={success_count} 失败={error_count} "
            f"空数据={empty_count} 总任务={total_jobs}"
        )
        task.error_log = merge_task_log(task.error_log, summary, "INFO" if error_count == 0 else "WARNING")
        if error_samples:
            task.error_log = merge_task_log(
                task.error_log,
                f"失败样本({min(len(error_samples), 30)}): " + " | ".join(error_samples[:10]),
                "ERROR",
            )
        await session.commit()
        logger.info(f"Batch financial collection completed: success={success_count}, errors={error_count}, total={total_jobs}")

        # 补采/批量财务任务结束后刷新覆盖率快照，供看板直接读取
        await self._refresh_coverage_snapshot_after_batch(task, year_ints)

    async def _refresh_coverage_snapshot_after_batch(
        self,
        task: CrawlerTask,
        years: List[int],
    ) -> None:
        """批量财务采集成功后异步刷新覆盖率快照。"""
        extra = task.extra_params if isinstance(task.extra_params, dict) else {}
        # 仅全量或明确 repair 任务刷新；避免无关局部实验污染主快照可再扩展
        should_refresh = bool(extra.get("repair")) or not task.target_companies
        if not should_refresh:
            return
        if task.status not in (CrawlerTaskStatus.SUCCESS,):
            # 有部分成功也刷新，便于看到最新缺口
            if (task.success_count or 0) <= 0:
                return

        try:
            from ..analysis.coverage_service import refresh_coverage_after_repair

            report_types = extra.get("report_types") or ["BS", "IS", "CF"]
            result = await refresh_coverage_after_repair(
                years=years,
                report_types=report_types,
                status_filter="active",
                trigger_task_id=task.id,
            )
            if result:
                logger.info(
                    "Coverage snapshot refreshed after task %s: snapshot_id=%s coverage=%s gaps=%s",
                    task.id,
                    result.get("snapshot_id"),
                    result.get("coverage_rate"),
                    result.get("gap_company_count"),
                )
                # 将刷新结果写回任务日志（新开 session 避免上面 session 状态不确定）
                async with async_session_factory() as log_session:
                    stmt = select(CrawlerTask).where(CrawlerTask.id == task.id)
                    t = (await log_session.execute(stmt)).scalar_one_or_none()
                    if t:
                        await append_task_log(
                            log_session,
                            t,
                            (
                                f"覆盖率快照已刷新 | snapshot_id={result.get('snapshot_id')} "
                                f"coverage={result.get('coverage_rate')} "
                                f"gap_companies={result.get('gap_company_count')} "
                                f"耗时={result.get('scan_duration_ms')}ms"
                            ),
                        )
        except Exception as e:
            logger.warning(f"Failed to refresh coverage snapshot after task {task.id}: {e}")

    async def _find_missing_data(
        self,
        session: AsyncSession,
        stock_codes: List[str],
        report_configs: List[tuple],
        years: List[int],
    ) -> Dict[str, List[str]]:
        """
        找出缺失的财务数据，支持断点续采。

        判定标准升级为：目标年份内，每个年份都必须具备该报表的
        全部必填核心科目；仅“有任意一条记录”不再视为完整。

        Returns:
            {report_type_str: [stock_code1, stock_code2, ...]}
        """
        missing: Dict[str, List[str]] = {rt_str: [] for rt_str, _, _ in report_configs}
        if not stock_codes or not years:
            return missing

        target_years = set(years)
        year_min = min(years)
        year_max = max(years)

        profile_by_company: Dict[str, str] = {}
        profile_rows = (
            await session.execute(
                select(Company.stock_code, Company.stock_name, Industry.code, Industry.name)
                .outerjoin(Industry, Company.industry_id == Industry.id)
                .where(Company.stock_code.in_(stock_codes))
            )
        ).all()
        for company_code, stock_name, industry_code, industry_name in profile_rows:
            profile_by_company[company_code] = validation_profile_for_industry(
                industry_code, industry_name, stock_name
            )

        for rt_str, rt_enum, _ in report_configs:
            required_by_profile = {
                profile: required_core_codes(rt_str, profile)
                for profile in set(profile_by_company.values()) | {"default"}
            }
            # 批量取出该报表在目标年份范围内的科目，避免 N 次按公司查询
            stmt = select(
                FinancialData.company_code,
                FinancialData.report_date,
                FinancialData.subject_code,
            ).where(
                FinancialData.company_code.in_(stock_codes),
                FinancialData.report_type == rt_enum,
                FinancialData.report_date >= date(year_min, 1, 1),
                FinancialData.report_date <= date(year_max, 12, 31),
            )
            rows = (await session.execute(stmt)).all()

            # company -> year -> {annual: set, any: set}
            # 优先用年报(12-31)判断完整度；若无年报再回退到该年任意期次
            present_by_company_year: Dict[str, Dict[int, Dict[str, set]]] = defaultdict(
                lambda: defaultdict(lambda: {"annual": set(), "any": set()})
            )
            for company_code, report_date, subject_code in rows:
                if not report_date or not subject_code:
                    continue
                y = report_date.year
                if y not in target_years:
                    continue
                bucket = present_by_company_year[company_code][y]
                bucket["any"].add(subject_code)
                if report_date.month == 12:
                    bucket["annual"].add(subject_code)

            for code in stock_codes:
                year_map = present_by_company_year.get(code, {})
                incomplete = False
                for y in target_years:
                    bucket = year_map.get(y) or {"annual": set(), "any": set()}
                    codes = bucket["annual"] or bucket["any"]
                    profile = profile_by_company.get(code, "default")
                    if not is_year_complete_for_resume(codes, rt_str, profile):
                        incomplete = True
                        break
                # 无核心科目定义时，回退：目标年都必须至少有一条
                if not required_by_profile.get(profile_by_company.get(code, "default")):
                    incomplete = any(
                        y not in year_map or not (year_map[y]["annual"] or year_map[y]["any"])
                        for y in target_years
                    )
                if incomplete:
                    missing[rt_str].append(code)

        return missing

    async def _execute_single_report_collection(
        self,
        service: CrawlerService,
        task: CrawlerTask,
        session: AsyncSession,
    ):
        """
        单公司逐表采集模式（原有逻辑保留）
        """
        report_type_map = {
            CrawlerDataType.BALANCE_SHEET: ("BS", ReportType.BS, "资产负债表"),
            CrawlerDataType.INCOME_STATEMENT: ("IS", ReportType.IS, "利润表"),
            CrawlerDataType.CASH_FLOW: ("CF", ReportType.CF, "现金流量表"),
        }

        data_type_mapping = {
            CrawlerDataType.BALANCE_SHEET: "BS",
            CrawlerDataType.INCOME_STATEMENT: "IS",
            CrawlerDataType.CASH_FLOW: "CF",
        }

        report_type_str = data_type_mapping.get(task.data_type)
        report_name = report_type_map.get(task.data_type, (None, None, str(task.data_type)))[2]
        if not report_type_str:
            await self._fail_task(session, task, f"Invalid data type {task.data_type}")
            return

        target_companies = task.target_companies or []
        total = len(target_companies)
        await append_task_log(
            session,
            task,
            f"单表采集启动 | 报表={report_name}({report_type_str}) | 公司数={total} | "
            f"目标={','.join(target_companies[:10])}{'...' if total > 10 else ''}",
        )

        if total == 0:
            await append_task_log(session, task, "目标公司列表为空，直接完成", level="WARNING")
            await service.complete_task(task, success=True)
            return

        success_count = 0
        error_count = 0

        for idx, stock_code in enumerate(target_companies):
            try:
                await append_task_log(
                    session,
                    task,
                    f"[{idx + 1}/{total}] 开始采集 {stock_code} {report_name}",
                    commit=False,
                )
                data_list = await service.crawl_financial_report(stock_code, report_type_str)
                if data_list:
                    save_summary = None
                    if hasattr(service, "save_to_db"):
                        save_summary = await service.save_to_db(
                            data_list, crawl_task_id=task.id
                        )
                    safe_rows = (
                        (save_summary or {}).get("inserted_rows", len(data_list))
                        + (save_summary or {}).get("updated_rows", 0)
                    )
                    if safe_rows:
                        success_count += 1
                        detail = (
                            f"{stock_code} 安全写入={safe_rows} "
                            f"未匹配={(save_summary or {}).get('unmatched_rows', 0)} "
                            f"歧义={(save_summary or {}).get('ambiguous_rows', 0)} "
                            f"拒绝={(save_summary or {}).get('rejected_rows', 0)} "
                            f"冲突={(save_summary or {}).get('conflict_rows', 0)}"
                        )
                        await service.update_task_progress(
                            task,
                            success_count,
                            error_count,
                            total,
                            detail=detail,
                        )
                    else:
                        error_count += 1
                        await service.update_task_progress(
                            task,
                            success_count,
                            error_count,
                            total,
                            error_log=f"{stock_code}: 未匹配到可安全落库的标准科目",
                            detail=f"{stock_code} 无安全科目匹配",
                        )
                else:
                    error_count += 1
                    await service.update_task_progress(
                        task,
                        success_count,
                        error_count,
                        total,
                        error_log=f"{stock_code}: 未获取到数据",
                        detail=f"{stock_code} 无数据",
                    )
            except Exception as e:
                logger.error(f"Error crawling {stock_code}: {e}")
                error_count += 1
                await service.update_task_progress(
                    task,
                    success_count,
                    error_count,
                    total,
                    error_log=f"{stock_code}: {e}",
                    detail=f"{stock_code} 异常",
                )

        await service.complete_task(task, success=(error_count == 0))

    async def _execute_qualitative_collection(
        self,
        service: QualitativeCrawlerService,
        task: CrawlerTask,
        session: AsyncSession,
    ):
        """
        定性数据采集模式

        流程：
        1. 获取目标公司列表
        2. 从 extra_params 读取 report_types 和 years
        3. 逐个公司采集年报/季报PDF，解析MD&A，写入数据库
        """
        target_codes = task.target_companies or []
        if not target_codes:
            logger.warning("Qualitative collection: no target companies specified")
            task.status = CrawlerTaskStatus.FAILED
            task.error_log = merge_task_log(task.error_log, "未指定目标公司", "ERROR")
            task.completed_at = datetime.utcnow()
            await session.commit()
            return

        # 读取额外参数
        extra = task.extra_params or {}
        report_types = extra.get("report_types", ["annual", "semi", "q1", "q3"])
        years = extra.get("years", [])
        if years and isinstance(years[0], str):
            years = [int(y) for y in years if str(y).isdigit()]
        else:
            years = [int(y) for y in years] if years else []

        if years:
            total = len(target_codes) * len(report_types) * len(years)
        else:
            total = len(target_codes) * len(report_types)
        # 进度按步骤计；报告条数记在日志，避免 progress 溢出
        step_success = 0
        step_failed = 0
        report_ok = 0
        report_fail = 0
        processed = 0
        await append_task_log(
            session,
            task,
            f"定性采集启动 | 公司={target_codes} | 报告类型={report_types} | 年份={years or '全部'} | 计划步骤={total}",
        )

        for stock_code in target_codes:
            for report_type in report_types:
                year_list = years if years else [None]
                for yr in year_list:
                    await append_task_log(
                        session,
                        task,
                        f"[{processed + 1}/{total}] 采集 {stock_code} {report_type}"
                        + (f" {yr}" if yr else ""),
                        commit=False,
                    )
                    result = await service._collect_qualitative_reports(stock_code, report_type, yr)
                    item_ok = result.get("collected", 0)
                    item_fail = result.get("failed", 0)
                    segs = result.get("segments_extracted", 0)
                    report_ok += item_ok
                    report_fail += item_fail
                    processed += 1
                    if item_fail > 0 and item_ok == 0:
                        step_failed += 1
                    else:
                        step_success += 1
                    await service.update_task_progress(
                        task,
                        step_success,
                        step_failed,
                        total,
                        detail=(
                            f"{stock_code} {report_type}{f' {yr}' if yr else ''} "
                            f"报告成功={item_ok} 报告失败={item_fail} 分部={segs} "
                            f"| 累计报告成功={report_ok}"
                        ),
                        error_log=(
                            f"{stock_code} {report_type}{f' {yr}' if yr else ''}: "
                            f"{item_fail} 份失败"
                            if item_fail
                            else None
                        ),
                    )
                    await asyncio.sleep(PER_COMPANY_DELAY)

        await append_task_log(
            session,
            task,
            f"定性采集汇总 | 步骤成功={step_success}/{total} 步骤失败={step_failed} "
            f"报告成功={report_ok} 报告失败={report_fail}",
        )
        await service.complete_task(task, success=(step_failed == 0))

    async def _execute_news_collection(
        self,
        service: NewsCrawlerService,
        task: CrawlerTask,
        session: AsyncSession,
    ):
        """
        新闻舆情采集模式

        流程：
        1. 获取目标公司列表
        2. 逐个公司采集新闻，情绪分析，写入数据库
        """
        target_codes = task.target_companies or []
        if not target_codes:
            logger.warning("News collection: no target companies specified")
            task.status = CrawlerTaskStatus.FAILED
            task.error_log = merge_task_log(task.error_log, "未指定目标公司", "ERROR")
            task.completed_at = datetime.utcnow()
            await session.commit()
            return

        total = len(target_codes)
        # 进度按「公司数」计量，避免 success_count=新闻条数 导致 progress 溢出
        company_done = 0
        company_failed = 0
        news_collected = 0
        await append_task_log(
            session,
            task,
            f"新闻舆情采集启动 | 公司数={total} | 目标={','.join(target_codes[:10])}",
        )

        for idx, stock_code in enumerate(target_codes):
            try:
                await append_task_log(
                    session,
                    task,
                    f"[{idx + 1}/{total}] 开始采集新闻 {stock_code}",
                    commit=False,
                )
                result = await service._collect_news(stock_code)
                collected = result.get("collected", 0)
                failed = result.get("failed", 0)
                news_collected += collected
                company_done += 1
                if failed > 0:
                    company_failed += 1
                await service.update_task_progress(
                    task,
                    company_done - company_failed,
                    company_failed,
                    total,
                    detail=(
                        f"{stock_code} 新增新闻={collected}"
                        + (f" 失败标记={failed}" if failed else "")
                        + f" | 累计新闻={news_collected}"
                    ),
                    error_log=f"{stock_code}: 采集失败" if failed else None,
                )
            except Exception as e:
                logger.error(f"Error collecting news for {stock_code}: {e}")
                company_done += 1
                company_failed += 1
                await service.update_task_progress(
                    task,
                    company_done - company_failed,
                    company_failed,
                    total,
                    error_log=f"{stock_code}: {e}",
                    detail=f"{stock_code} 异常 | 累计新闻={news_collected}",
                )

        # 在日志中保留新闻条数，success_count 仍按成功公司数
        await append_task_log(
            session,
            task,
            f"新闻采集汇总 | 公司成功={company_done - company_failed}/{total} "
            f"公司失败={company_failed} 新闻入库={news_collected}",
        )
        # 额外把新闻条数写入 total 语义不够准确时，用 extra 字段风格记在日志即可
        await service.complete_task(task, success=(company_failed == 0))

    def _create_service(self, session: AsyncSession, source_code: str) -> Optional[CrawlerService]:
        """根据代码创建服务实例"""
        if source_code == "sina":
            return SinaCrawlerService(session)
        elif source_code == "exchange_api":
            return ExchangeCrawler(session)
        elif source_code == "cninfo":
            return QualitativeCrawlerService(session)
        elif source_code == "sina_news":
            return NewsCrawlerService(session)
        return None

    async def _fail_task(self, session: AsyncSession, task: CrawlerTask, error_msg: str):
        """标记任务失败"""
        task.status = CrawlerTaskStatus.FAILED
        task.error_log = merge_task_log(task.error_log, f"任务失败: {error_msg}", "ERROR")
        task.completed_at = datetime.utcnow()
        await session.commit()


# 全局单例
crawler_engine = CrawlerEngine()
