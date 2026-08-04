# -*- coding: utf-8 -*-
"""从一个新浪财经财报样本补录空的标准科目 sina_name。

只使用经过当前安全匹配器验证的来源字段：标准名、已审核主名称、来源别名或
确定性归一化匹配。需要父级上下文、匹配歧义、合并披露和口径不一致的字段不会
更新到 account_subjects.sina_name。

默认 dry-run；传入 --apply 后才在单个事务中更新空值字段。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.crawler.sina_crawler import SinaCrawlerService
from backend.crawler.subject_matching import SinaSubjectMatcher
from backend.persistence.db import async_session_factory, engine
from backend.persistence.financial_models import (
    AccountSubject,
    AccountSubjectSourceAlias,
)

SAFE_UNCONTEXTUAL_METHODS = {
    "name_exact",
    "sina_name_exact",
    "source_alias_exact",
    "normalized_exact",
}


def _report_type_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").upper()


async def fetch_source_rows(
    stock_code: str,
    report_types: Sequence[str],
) -> List[Dict[str, Any]]:
    """读取新浪公开 JSON 报表字段，不落库。"""
    rows: List[Dict[str, Any]] = []
    service = SinaCrawlerService(None)
    async with service:
        for report_type in report_types:
            rows.extend(await service.crawl_financial_report(stock_code, report_type))
    return rows


async def build_candidates(
    source_rows: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    """基于真实来源字段构建空 sina_name 的安全主名称候选。"""
    async with async_session_factory() as session:
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

    matcher = SinaSubjectMatcher(subjects, aliases)
    subjects_by_code = {subject.code: subject for subject in subjects}
    empty_codes = {
        subject.code
        for subject in subjects
        if not str(subject.sina_name or "").strip()
    }
    raw_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    method_counts: Counter[str] = Counter()
    skipped: Counter[str] = Counter()
    skipped_examples: Dict[str, set[str]] = defaultdict(set)

    for row in source_rows:
        raw_name = str(row.get("raw_subject_name") or row.get("subject_name") or "").strip()
        report_type = str(row.get("report_type") or "").upper()
        context_name = str(row.get("source_context_name") or "").strip()
        if not raw_name or not report_type:
            continue

        contextual = matcher.match(raw_name, report_type, context_name)
        if not contextual.matched:
            reason = contextual.issue_type or "unmatched"
            skipped[reason] += 1
            skipped_examples[reason].add(f"{report_type}:{raw_name}")
            continue
        if contextual.method == "context_alias_exact":
            skipped["contextual"] += 1
            skipped_examples["contextual"].add(f"{report_type}:{raw_name}")
            continue

        # sina_name 是无上下文主名称，必须证明脱离层级也仍能唯一命中同一标准科目。
        uncontextual = matcher.match(raw_name, report_type)
        if (
            not uncontextual.matched
            or uncontextual.subject.code != contextual.subject.code
            or uncontextual.method not in SAFE_UNCONTEXTUAL_METHODS
        ):
            skipped["context_dependent"] += 1
            skipped_examples["context_dependent"].add(f"{report_type}:{raw_name}")
            continue

        subject = uncontextual.subject
        if subject.code not in empty_codes:
            skipped["already_populated"] += 1
            continue
        raw_counts[subject.code][raw_name] += 1
        method_counts[uncontextual.method] += 1

    candidates: List[Dict[str, Any]] = []
    for code, counts in sorted(raw_counts.items()):
        ranked = counts.most_common()
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            skipped["primary_name_tie"] += sum(counts.values())
            skipped_examples["primary_name_tie"].add(
                f"{_report_type_value(subjects_by_code[code].report_type)}:{code}"
            )
            continue
        subject = subjects_by_code[code]
        chosen_name, occurrence_count = ranked[0]
        candidates.append({
            "subject_id": subject.id,
            "subject_code": subject.code,
            "standard_name": subject.name,
            "report_type": _report_type_value(subject.report_type),
            "sina_name": chosen_name,
            "occurrence_count": occurrence_count,
            "source_variants": [
                {"name": name, "count": count}
                for name, count in ranked
            ],
        })

    return {
        "candidate_count": len(candidates),
        "candidates": candidates,
        "method_counts": dict(sorted(method_counts.items())),
        "skipped_counts": dict(sorted(skipped.items())),
        "skipped_examples": {
            reason: sorted(examples)[:12]
            for reason, examples in sorted(skipped_examples.items())
        },
    }


async def apply_candidates(candidates: Sequence[Mapping[str, Any]]) -> int:
    """只填充仍为空的 sina_name，且在同一个事务内提交。"""
    updated = 0
    async with async_session_factory() as session:
        for candidate in candidates:
            subject = (
                await session.execute(
                    select(AccountSubject).where(
                        AccountSubject.id == candidate["subject_id"])
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if subject is None:
                raise RuntimeError(f"标准科目不存在: {candidate['subject_code']}")
            if str(subject.sina_name or "").strip():
                continue
            if _report_type_value(subject.report_type) != candidate["report_type"]:
                raise RuntimeError(f"标准科目报表类型已变化: {candidate['subject_code']}")
            subject.sina_name = str(candidate["sina_name"])
            updated += 1
        await session.commit()
    return updated


def print_report(stock_code: str, report_types: Sequence[str], report: Mapping[str, Any]) -> None:
    print(f"Sina 主名称候选 | stock={stock_code} reports={','.join(report_types)}")
    print(f"- candidate_count: {report['candidate_count']}")
    print(f"- method_counts: {report['method_counts']}")
    print(f"- skipped_counts: {report['skipped_counts']}")
    print("- candidates:")
    for candidate in report["candidates"]:
        variants = ", ".join(
            f"{item['name']}({item['count']})"
            for item in candidate["source_variants"]
        )
        print(
            "  "
            f"{candidate['report_type']} {candidate['subject_code']} "
            f"{candidate['standard_name']} -> {candidate['sina_name']} "
            f"| variants={variants}"
        )
    if report["skipped_examples"]:
        print(f"- skipped_examples: {report['skipped_examples']}")


async def main(stock_code: str, report_types: Sequence[str], apply: bool) -> None:
    try:
        source_rows = await fetch_source_rows(stock_code, report_types)
        report = await build_candidates(source_rows)
        print_report(stock_code, report_types, report)
        if not apply:
            print("未传入 --apply：未修改数据库。")
            return
        updated = await apply_candidates(report["candidates"])
        print(f"应用结果: updated_sina_name_count={updated}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从新浪样本补录空 sina_name")
    parser.add_argument("--stock-code", default="600519", help="新浪样本股票代码")
    parser.add_argument(
        "--report-types",
        default="BS,IS,CF",
        help="报表类型，逗号分隔",
    )
    parser.add_argument("--apply", action="store_true", help="在单一事务中更新空 sina_name")
    args = parser.parse_args()
    report_types = [
        report_type.strip().upper()
        for report_type in args.report_types.split(",")
        if report_type.strip().upper() in {"BS", "IS", "CF"}
    ]
    if not report_types:
        raise SystemExit("至少指定一个有效报表类型: BS,IS,CF")
    asyncio.run(main(args.stock_code, report_types, args.apply))
