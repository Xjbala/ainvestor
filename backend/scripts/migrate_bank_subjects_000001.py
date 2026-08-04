# -*- coding: utf-8 -*-
"""将审核后的 000001 银行标准科目和新浪映射增量写入生产目录。

默认只输出 dry-run 报告。--apply 才会在单个事务中创建缺失标准科目、补齐空的
sina_name 并写入来源别名；绝不重写已有 code/name/report_type 或历史财务数据。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.crawler.subject_matching import normalize_subject_name
from backend.persistence.db import async_session_factory, engine
from backend.persistence.financial_models import (
    AccountCategory,
    AccountSubject,
    AccountSubjectSourceAlias,
    ReportType,
)
from backend.scripts.bank_subject_catalog import load_bank_subject_catalog


def _report_type_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").upper()


def _alias_key(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(entry["report_type"]).upper(),
        str(entry["source_name"]).strip(),
        str(entry.get("context_name") or "").strip(),
    )


async def build_report() -> Dict[str, Any]:
    """校验银行标准目录对现有权威科目表的增量是否安全。"""
    catalog = load_bank_subject_catalog()
    async with async_session_factory() as session:
        subjects = (await session.execute(select(AccountSubject))).scalars().all()
        categories = (await session.execute(select(AccountCategory))).scalars().all()
        aliases = (
            await session.execute(
                select(AccountSubjectSourceAlias)
                .options(selectinload(AccountSubjectSourceAlias.subject))
                .where(AccountSubjectSourceAlias.source == "sina")
            )
        ).scalars().all()

    subjects_by_code = {subject.code: subject for subject in subjects}
    categories_by_code = {category.code: category for category in categories}
    invalid_subjects: List[Dict[str, Any]] = []
    existing_subject_conflicts: List[Dict[str, Any]] = []
    new_subject_codes: List[str] = []
    code_names: Dict[tuple[str, str], str] = {}

    for entry in catalog["subjects"]:
        code = str(entry["code"]).strip()
        name = str(entry["name"]).strip()
        report_type = str(entry["report_type"]).upper()
        category_code = str(entry["category_code"]).strip()
        if not code or not name or report_type not in {"BS", "IS", "CF"}:
            invalid_subjects.append({"entry": entry, "reason": "缺少编码、名称或有效报表类型"})
            continue
        if category_code not in categories_by_code:
            invalid_subjects.append({"entry": entry, "reason": f"分类不存在: {category_code}"})
            continue
        category = categories_by_code[category_code]
        if _report_type_value(category.report_type) != report_type:
            invalid_subjects.append({"entry": entry, "reason": "分类报表类型不一致"})
            continue
        name_key = (report_type, name)
        if name_key in code_names and code_names[name_key] != code:
            invalid_subjects.append({"entry": entry, "reason": "目录内同报表类型名称重复"})
            continue
        code_names[name_key] = code

        existing = subjects_by_code.get(code)
        if existing is None:
            new_subject_codes.append(code)
            continue
        if (
            existing.name != name
            or _report_type_value(existing.report_type) != report_type
            or existing.category_id != category.id
        ):
            existing_subject_conflicts.append({
                "code": code,
                "catalog_name": name,
                "existing_name": existing.name,
                "catalog_report_type": report_type,
                "existing_report_type": _report_type_value(existing.report_type),
                "catalog_category": category_code,
                "existing_category_id": existing.category_id,
            })

    known_codes = set(subjects_by_code) | set(new_subject_codes)
    alias_keys = Counter(_alias_key(entry) for entry in catalog["aliases"])
    duplicate_catalog_aliases = [
        {"report_type": key[0], "source_name": key[1], "context_name": key[2], "count": count}
        for key, count in alias_keys.items()
        if count > 1
    ]
    invalid_aliases: List[Dict[str, Any]] = []
    for entry in catalog["aliases"]:
        code = str(entry["subject_code"])
        if code not in known_codes:
            invalid_aliases.append({"entry": entry, "reason": "目标标准科目不存在"})
            continue
        subject = subjects_by_code.get(code)
        if subject and _report_type_value(subject.report_type) != str(entry["report_type"]).upper():
            invalid_aliases.append({"entry": entry, "reason": "来源别名报表类型与标准科目不一致"})

    existing_aliases = {
        (
            _report_type_value(alias.report_type),
            alias.source_name,
            alias.context_name or "",
        ): alias
        for alias in aliases
    }
    alias_updates: List[Dict[str, Any]] = []
    for entry in catalog["aliases"]:
        key = _alias_key(entry)
        existing = existing_aliases.get(key)
        if existing and existing.subject.code != entry["subject_code"]:
            alias_updates.append({
                "report_type": key[0],
                "source_name": key[1],
                "context_name": key[2],
                "existing_subject_code": existing.subject.code,
                "catalog_subject_code": entry["subject_code"],
            })

    return {
        "source_sample": catalog["source_sample"],
        "existing_subject_count": len(subjects),
        "new_subject_count": len(new_subject_codes),
        "new_subject_codes": new_subject_codes,
        "alias_count": len(catalog["aliases"]),
        "invalid_subjects": invalid_subjects,
        "existing_subject_conflicts": existing_subject_conflicts,
        "duplicate_catalog_aliases": duplicate_catalog_aliases,
        "invalid_aliases": invalid_aliases,
        "alias_updates": alias_updates,
        "rejected_source_fields": catalog["rejected"],
    }


async def apply_catalog(report: Mapping[str, Any]) -> Dict[str, int]:
    """在单个事务内应用通过 dry-run 的银行科目和来源别名。"""
    blocking_keys = (
        "invalid_subjects",
        "existing_subject_conflicts",
        "duplicate_catalog_aliases",
        "invalid_aliases",
    )
    if any(report.get(key) for key in blocking_keys):
        raise RuntimeError("银行科目 dry-run 存在冲突，拒绝写入")

    catalog = load_bank_subject_catalog()
    created_subjects = 0
    updated_primary_names = 0
    created_aliases = 0
    updated_aliases = 0

    async with async_session_factory() as session:
        subjects_by_code = {
            subject.code: subject
            for subject in (await session.execute(select(AccountSubject))).scalars().all()
        }
        categories_by_code = {
            category.code: category
            for category in (await session.execute(select(AccountCategory))).scalars().all()
        }
        for entry in catalog["subjects"]:
            code = str(entry["code"])
            subject = subjects_by_code.get(code)
            if subject is None:
                subject = AccountSubject(
                    code=code,
                    name=str(entry["name"]),
                    sina_name=entry.get("sina_name") or None,
                    category_id=categories_by_code[entry["category_code"]].id,
                    report_type=ReportType(str(entry["report_type"]).upper()),
                    subject_category=str(entry["subject_category"]),
                    description=entry.get("description"),
                    is_summary=bool(entry.get("is_summary", False)),
                    sort_order=int(entry.get("sort_order", 0)),
                    legacy_is_financial=False,
                )
                session.add(subject)
                subjects_by_code[code] = subject
                created_subjects += 1
            elif not str(subject.sina_name or "").strip() and entry.get("sina_name"):
                subject.sina_name = str(entry["sina_name"])
                updated_primary_names += 1

        await session.flush()
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
        for entry in catalog["aliases"]:
            key = _alias_key(entry)
            source_name = key[1]
            existing = existing_aliases.get(key)
            if existing:
                expected_subject_id = subjects_by_code[entry["subject_code"]].id
                if existing.subject_id != expected_subject_id:
                    existing.subject_id = expected_subject_id
                    existing.normalized_name = normalize_subject_name(source_name)
                    existing.note = entry.get("note")
                    existing.is_active = True
                    updated_aliases += 1
                continue
            session.add(
                AccountSubjectSourceAlias(
                    subject_id=subjects_by_code[entry["subject_code"]].id,
                    source="sina",
                    report_type=ReportType(key[0]),
                    source_name=source_name,
                    normalized_name=normalize_subject_name(source_name),
                    context_name=key[2],
                    note=entry.get("note"),
                    is_active=True,
                )
            )
            created_aliases += 1
        await session.commit()

    return {
        "created_subjects": created_subjects,
        "updated_primary_sina_names": updated_primary_names,
        "created_source_aliases": created_aliases,
        "updated_source_aliases": updated_aliases,
    }


def print_report(report: Mapping[str, Any]) -> None:
    print("000001 银行科目 dry-run 报告")
    for key, value in report.items():
        print(f"- {key}: {value}")


async def main(apply: bool) -> None:
    try:
        report = await build_report()
        print_report(report)
        if not apply:
            print("未传入 --apply：未修改数据库。")
            return
        print(f"应用结果: {await apply_catalog(report)}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="补录 000001 银行标准科目与新浪映射")
    parser.add_argument("--apply", action="store_true", help="在单个事务中写入通过审核的目录")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
