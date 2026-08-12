# -*- coding: utf-8 -*-
"""将已确认停止但仍显示运行中的会话修复为 cancelled。"""

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from backend.persistence.db import engine


async def repair_sessions(session_ids: list[str]) -> None:
    """只修复调用方明确指定的会话，避免影响真实运行任务。"""
    async with engine.begin() as conn:
        for session_id in session_ids:
            result = await conn.execute(
                text(
                    "SELECT status FROM analysis_sessions WHERE id = :session_id",
                ),
                {"session_id": session_id},
            )
            status = result.scalar_one_or_none()
            if status is None:
                print(f"{session_id}: 会话不存在，跳过")
                continue
            if status == "cancelled":
                print(f"{session_id}: 已是 cancelled，无需修复")
                continue
            if status not in {"pending", "running"}:
                print(f"{session_id}: 当前状态为 {status}，跳过")
                continue

            await conn.execute(
                text(
                    "UPDATE analysis_sessions "
                    "SET status = 'cancelled', completed_at = COALESCE(completed_at, NOW()) "
                    "WHERE id = :session_id",
                ),
                {"session_id": session_id},
            )
            print(f"{session_id}: 已更新为 cancelled")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="修复已确认停止但仍为 running/pending 的分析会话",
    )
    parser.add_argument(
        "--session-id",
        dest="session_ids",
        action="append",
        required=True,
        help="需要修复的会话 ID；可重复传入",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(repair_sessions(args.session_ids))
