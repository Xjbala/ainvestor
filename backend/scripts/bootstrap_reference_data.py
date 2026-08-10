# -*- coding: utf-8 -*-
"""一键引导生产数据库参考数据。

按依赖顺序执行：
  1. 创建数据库表（create_all，幂等）
  2. 初始化标准科目（含完整利润表 ISF001-ISF028 序列）
  3. 初始化数据源与交易所
  4. 补录新浪科目映射（主名称 + 来源别名）
  5. 补录 000001 银行扩展科目与映射

每一步都是幂等的：已存在的行跳过，不覆盖已有定义。
如果新浪/银行映射 dry-run 发现冲突，跳过该步写入但继续后续步骤。

用法:
    # 完整执行（生产环境首次部署）
    uv run python -m backend.scripts.bootstrap_reference_data

    # 仅审计不写入
    uv run python -m backend.scripts.bootstrap_reference_data --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.persistence.db import engine, init_database
from backend.scripts.init_subjects import init_subjects
from backend.scripts.init_data import init_data
from backend.scripts.migrate_sina_subject_mappings import (
    ensure_schema as ensure_sina_schema,
    build_report as build_sina_report,
    apply_mapping_catalog as apply_sina_mapping,
)
from backend.scripts.migrate_bank_subjects_000001 import (
    build_report as build_bank_report,
    apply_catalog as apply_bank_catalog,
)

SINA_BLOCKING_KEYS = (
    "missing_or_invalid",
    "primary_sina_name_conflicts",
    "duplicate_catalog_aliases",
    "existing_alias_conflicts",
)
BANK_BLOCKING_KEYS = (
    "invalid_subjects",
    "existing_subject_conflicts",
    "duplicate_catalog_aliases",
    "invalid_aliases",
)


def _has_blocking(report: dict, keys: tuple[str, ...]) -> bool:
    return any(report.get(k) for k in keys)


def _print_report(title: str, report: dict) -> None:
    print(f"\n{'=' * 60}")
    print(title)
    print(f"{'=' * 60}")
    for key, value in report.items():
        print(f"  {key}: {value}")


async def bootstrap(dry_run: bool = False) -> None:
    try:
        # === 1/5 创建数据库表 ===
        print("\n[1/5] 创建数据库表...")
        await init_database()
        print("  数据库表就绪")

        # === 2/5 初始化标准科目 ===
        print("\n[2/5] 初始化标准科目...")
        await init_subjects()
        print("  标准科目就绪")

        # === 3/5 初始化数据源与交易所 ===
        print("\n[3/5] 初始化数据源与交易所...")
        await init_data()
        print("  数据源与交易所就绪")

        # === 4/5 补录新浪科目映射 ===
        print("\n[4/5] 新浪科目映射...")
        await ensure_sina_schema()
        sina_report = await build_sina_report()
        _print_report("新浪映射审计报告", sina_report)

        if dry_run:
            print("  --dry-run 模式：跳过新浪映射写入")
        elif _has_blocking(sina_report, SINA_BLOCKING_KEYS):
            print("  新浪映射存在冲突，跳过写入；请单独运行 migrate_sina_subject_mappings.py --dry-run 排查")
        else:
            result = await apply_sina_mapping(sina_report)
            _print_report("新浪映射写入结果", result)

        # === 5/5 补录银行科目 ===
        print("\n[5/5] 000001 银行扩展科目...")
        bank_report = await build_bank_report()
        _print_report("银行科目审计报告", bank_report)

        if dry_run:
            print("  --dry-run 模式：跳过银行科目写入")
        elif _has_blocking(bank_report, BANK_BLOCKING_KEYS):
            print("  银行科目存在冲突，跳过写入；请单独运行 migrate_bank_subjects_000001.py --dry-run 排查")
        else:
            result = await apply_bank_catalog(bank_report)
            _print_report("银行科目写入结果", result)

        print("\n" + "=" * 60)
        if dry_run:
            print("引导数据审计完成（--dry-run，未写入）")
        else:
            print("引导数据初始化完成")
        print("=" * 60)

    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="一键引导生产数据库参考数据")
    parser.add_argument(
        "--dry-run", action="store_true", help="仅审计不写入"
    )
    args = parser.parse_args()
    asyncio.run(bootstrap(dry_run=args.dry_run))
