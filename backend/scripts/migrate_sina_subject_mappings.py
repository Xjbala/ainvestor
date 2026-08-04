# -*- coding: utf-8 -*-
"""为现有标准科目表补录已审核的新浪名称和来源别名。

默认 dry-run，只输出审计报告；传入 --apply 后才会创建新增表/列并写入映射。
该脚本从不创建或修改 account_subjects 的 code、name、report_type，也不会改写已有
非空 sina_name 或历史 financial_data。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import inspect, select, text

from backend.crawler.subject_matching import normalize_subject_name
from backend.persistence.db import async_session_factory, engine
from backend.persistence.financial_models import (
    AccountSubject,
    AccountSubjectSourceAlias,
    FinancialMatchIssue,
    ReportType,
)
from backend.scripts.sina_mapping_catalog import load_sina_subject_mapping_catalog


def _report_type_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").upper()


def _table_columns(sync_connection, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(sync_connection).get_columns(table_name)}


async def _table_exists(table_name: str) -> bool:
    async with engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table(table_name)
        )


async def _existing_columns(table_name: str) -> set[str]:
    if not await _table_exists(table_name):
        return set()
    async with engine.connect() as conn:
        return await conn.run_sync(lambda sync_conn: _table_columns(sync_conn, table_name))


async def ensure_schema() -> None:
    """仅创建新表及向 financial_data 添加可空溯源列。"""
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: AccountSubjectSourceAlias.__table__.create(
                sync_conn, checkfirst=True
            )
        )
        await conn.run_sync(
            lambda sync_conn: FinancialMatchIssue.__table__.create(
                sync_conn, checkfirst=True
            )
        )

        columns = await conn.run_sync(
            lambda sync_conn: _table_columns(sync_conn, "financial_data")
        )
        dialect = conn.dialect.name
        column_types = {
            "source_subject_name": "VARCHAR(200)",
            "source_context_name": "VARCHAR(200)",
            "subject_match_method": "VARCHAR(50)",
        }
        for name, column_type in column_types.items():
            if name not in columns:
                await conn.execute(
                    text(f"ALTER TABLE financial_data ADD COLUMN {name} {column_type} NULL")
                )

        # MySQL/SQLite 对新增索引的 if-not-exists 兼容性不同；模型表索引由 create_all
        # 负责，新列仅需可追溯数据即可。
        if dialect not in {"mysql", "sqlite"}:
            raise RuntimeError(f"未支持的数据库方言: {dialect}")


async def build_report() -> Dict[str, Any]:
    """检查现有标准目录与已审核新浪映射之间的契约。"""
    catalog = load_sina_subject_mapping_catalog()
    desired = list(catalog["primary_sina_names"]) + list(catalog["aliases"])

    alias_table_exists = await _table_exists("account_subject_source_aliases")
    async with async_session_factory() as session:
        subjects = (await session.execute(select(AccountSubject))).scalars().all()
        aliases = []
        if alias_table_exists:
            aliases = (
                await session.execute(
                    select(AccountSubjectSourceAlias).where(
                        AccountSubjectSourceAlias.source == "sina"
                    )
                )
            ).scalars().all()

    by_code = {subject.code: subject for subject in subjects}
    issues: List[Dict[str, Any]] = []
    valid_count = 0
    primary_conflicts: List[Dict[str, Any]] = []
    alias_keys: Counter[tuple[str, str, str]] = Counter()

    for entry in desired:
        code = str(entry["subject_code"])
        report_type = str(entry["report_type"]).upper()
        subject = by_code.get(code)
        if subject is None:
            issues.append({
                "kind": "missing_subject",
                "subject_code": code,
                "report_type": report_type,
                "source_name": entry.get("sina_name") or entry.get("source_name"),
            })
            continue
        if _report_type_value(subject.report_type) != report_type:
            issues.append({
                "kind": "report_type_mismatch",
                "subject_code": code,
                "expected_report_type": report_type,
                "actual_report_type": _report_type_value(subject.report_type),
                "source_name": entry.get("sina_name") or entry.get("source_name"),
            })
            continue

        if "sina_name" in entry:
            current = str(subject.sina_name or "").strip()
            wanted = str(entry["sina_name"]).strip()
            if current and current != wanted:
                primary_conflicts.append({
                    "subject_code": code,
                    "existing_sina_name": current,
                    "catalog_sina_name": wanted,
                })
        else:
            key = (
                report_type,
                str(entry["source_name"]).strip(),
                str(entry.get("context_name") or "").strip(),
            )
            alias_keys[key] += 1
        valid_count += 1

    duplicate_catalog_aliases = [
        {"report_type": key[0], "source_name": key[1], "context_name": key[2], "count": count}
        for key, count in alias_keys.items()
        if count > 1
    ]
    existing_alias_keys = Counter(
        (
            _report_type_value(alias.report_type),
            alias.source_name,
            alias.context_name or "",
        )
        for alias in aliases
    )
    existing_alias_conflicts = [
        {"report_type": key[0], "source_name": key[1], "context_name": key[2], "count": count}
        for key, count in existing_alias_keys.items()
        if count > 1
    ]

    return {
        "standard_subject_count": len(subjects),
        "catalog_mapping_count": len(desired),
        "valid_catalog_mapping_count": valid_count,
        "missing_or_invalid": issues,
        "primary_sina_name_conflicts": primary_conflicts,
        "duplicate_catalog_aliases": duplicate_catalog_aliases,
        "existing_alias_conflicts": existing_alias_conflicts,
        "rejected_mapping_count": len(catalog["rejected"]),
        "rejected_mappings": catalog["rejected"],
    }


async def apply_mapping_catalog(report: Mapping[str, Any]) -> Dict[str, int]:
    """将无冲突的审核目录写入现有标准科目；调用方必须先完成 dry-run。"""
    blocking_keys = (
        "missing_or_invalid",
        "primary_sina_name_conflicts",
        "duplicate_catalog_aliases",
        "existing_alias_conflicts",
    )
    if any(report.get(key) for key in blocking_keys):
        raise RuntimeError("映射审计存在冲突，拒绝写入；请先处理 dry-run 报告")

    catalog = load_sina_subject_mapping_catalog()
    created_aliases = 0
    updated_primary_names = 0

    async with async_session_factory() as session:
        subjects = {
            subject.code: subject
            for subject in (await session.execute(select(AccountSubject))).scalars().all()
        }
        existing_aliases = {
            (
                _report_type_value(alias.report_type),
                alias.source_name,
                alias.context_name or "",
            ): alias
            for alias in (
                await session.execute(
                    select(AccountSubjectSourceAlias).where(
                        AccountSubjectSourceAlias.source == "sina"
                    )
                )
            ).scalars().all()
        }

        for entry in catalog["primary_sina_names"]:
            subject = subjects[entry["subject_code"]]
            if not str(subject.sina_name or "").strip():
                subject.sina_name = entry["sina_name"]
                updated_primary_names += 1

        for entry in catalog["aliases"]:
            report_type = str(entry["report_type"]).upper()
            source_name = str(entry["source_name"]).strip()
            context_name = str(entry.get("context_name") or "").strip()
            key = (report_type, source_name, context_name)
            if key in existing_aliases:
                continue
            session.add(
                AccountSubjectSourceAlias(
                    subject_id=subjects[entry["subject_code"]].id,
                    source="sina",
                    report_type=ReportType(report_type),
                    source_name=source_name,
                    normalized_name=normalize_subject_name(source_name),
                    context_name=context_name,
                    note=entry.get("note"),
                    is_active=True,
                )
            )
            created_aliases += 1

        await session.commit()

    return {
        "updated_primary_sina_names": updated_primary_names,
        "created_source_aliases": created_aliases,
    }


async def audit_historical_sina_data() -> Dict[str, Any]:
    """只读审计历史新浪数据的可追溯性，不对历史数值作任何改写。"""
    if not await _table_exists("financial_data"):
        return {
            "historical_sina_row_count": 0,
            "trace_columns_exist": False,
            "traceable_row_count": 0,
            "untraceable_row_count": 0,
            "task_id_count": 0,
            "note": "financial_data 表不存在。",
        }

    columns = await _existing_columns("financial_data")
    trace_columns_exist = {
        "source_subject_name",
        "source_context_name",
        "subject_match_method",
    }.issubset(columns)
    traceable_expression = (
        "SUM(CASE WHEN source_subject_name IS NOT NULL "
        "AND subject_match_method IS NOT NULL THEN 1 ELSE 0 END)"
        if trace_columns_exist
        else "0"
    )
    query = text(
        "SELECT COUNT(*) AS total, "
        f"{traceable_expression} AS traceable, "
        "COUNT(DISTINCT crawl_task_id) AS task_id_count "
        "FROM financial_data WHERE data_source = :source"
    )
    async with engine.connect() as conn:
        row = (await conn.execute(query, {"source": "sina"})).mappings().one()

    total = int(row["total"] or 0)
    traceable = int(row["traceable"] or 0)
    return {
        "historical_sina_row_count": total,
        "trace_columns_exist": trace_columns_exist,
        "traceable_row_count": traceable,
        "untraceable_row_count": total - traceable,
        "task_id_count": int(row["task_id_count"] or 0),
        "note": "历史行没有原始新浪字段时无法安全重映射；应在补录后按需重采。",
    }


def _print_report(title: str, payload: Mapping[str, Any]) -> None:
    print(title)
    for key, value in payload.items():
        print(f"- {key}: {value}")


async def main(apply: bool, audit_history: bool) -> None:
    try:
        report = await build_report()
        _print_report("新浪映射 dry-run 报告", report)

        if audit_history:
            _print_report("历史新浪数据审计", await audit_historical_sina_data())

        if not apply:
            print("未传入 --apply：未修改数据库。")
            return

        if report["standard_subject_count"] == 0:
            raise RuntimeError("account_subjects 为空，拒绝写入；请连接包含权威科目表的生产库")
        await ensure_schema()
        _print_report("应用结果", await apply_mapping_catalog(report))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="补录审核后的新浪科目映射")
    parser.add_argument("--apply", action="store_true", help="显式执行新增表/列和映射写入")
    parser.add_argument("--audit-history", action="store_true", help="输出历史新浪数据可追溯性审计")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply, audit_history=args.audit_history))
