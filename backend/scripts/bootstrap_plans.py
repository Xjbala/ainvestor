# -*- coding: utf-8 -*-
"""引导订阅计划目录。

幂等创建默认 plans（free/pro/enterprise）。已存在的计划会被更新为
脚本中定义的最新值——这样改额度时只需改本脚本并重新执行。

用法:
    uv run python -m backend.scripts.bootstrap_plans
    uv run python -m backend.scripts.bootstrap_plans --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.persistence.db import async_session_factory, engine, init_database
from backend.persistence.repository import PlanRepository

# 默认计划定义。修改额度时改这里并重新执行脚本即可生效。
DEFAULT_PLANS = [
    {
        "code": "free",
        "name": "免费版",
        "ai_quota_monthly": 3,
        "expert_quota_monthly": 10,
        "data_api_quota_monthly": 0,
        "price_cents": 0,
        "is_active": True,
        "sort_order": 0,
    },
    {
        "code": "pro",
        "name": "专业版",
        "ai_quota_monthly": 50,
        "expert_quota_monthly": 200,
        "data_api_quota_monthly": 1000,
        "price_cents": 9900,
        "is_active": True,
        "sort_order": 10,
    },
    {
        "code": "enterprise",
        "name": "企业版",
        "ai_quota_monthly": 500,
        "expert_quota_monthly": 2000,
        "data_api_quota_monthly": 20000,
        "price_cents": 99000,
        "is_active": True,
        "sort_order": 20,
    },
]


async def bootstrap_plans(dry_run: bool = False) -> None:
    # 确保表已存在（幂等）
    await init_database()

    async with async_session_factory() as session:
        repo = PlanRepository(session)
        print(f"\n{'=' * 60}")
        print("订阅计划引导")
        print(f"{'=' * 60}")

        for plan_def in DEFAULT_PLANS:
            existing = await repo.get_by_code(plan_def["code"])
            action = "新建" if existing is None else "更新"
            print(
                f"  [{action}] {plan_def['code']:<12} "
                f"ai={plan_def['ai_quota_monthly']:>4} "
                f"expert={plan_def['expert_quota_monthly']:>4} "
                f"data_api={plan_def['data_api_quota_monthly']:>5} "
                f"price={plan_def['price_cents']:>7}分"
            )

            if not dry_run:
                await repo.upsert(**plan_def)

        if dry_run:
            print("\n--dry-run 模式：未写入")
        else:
            await session.commit()
            print("\n订阅计划引导完成")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="引导订阅计划目录")
    parser.add_argument(
        "--dry-run", action="store_true", help="仅审计不写入"
    )
    args = parser.parse_args()
    try:
        asyncio.run(bootstrap_plans(dry_run=args.dry_run))
    finally:
        asyncio.run(engine.dispose())
