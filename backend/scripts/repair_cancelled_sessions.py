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


def normalize_status(status: object) -> str:
    """规范化不同历史库返回的会话状态值。"""
    return str(getattr(status, "value", status)).lower()


def cancelled_status_for(status: object) -> str:
    """兼容旧 MySQL ENUM 的大写状态值。"""
    raw_status = str(getattr(status, "value", status))
    return "CANCELLED" if raw_status.isupper() else "cancelled"


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
            normalized_status = normalize_status(status)
            if normalized_status == "cancelled":
                print(f"{session_id}: 已是 cancelled，无需修复")
                continue
            if normalized_status not in {"pending", "running"}:
                print(f"{session_id}: 当前状态为 {status}，跳过")
                continue

            await conn.execute(
                text(
                    "UPDATE analysis_sessions "
                    "SET status = :cancelled_status, completed_at = COALESCE(completed_at, NOW()) "
                    "WHERE id = :session_id",
                ),
                {
                    "cancelled_status": cancelled_status_for(status),
                    "session_id": session_id,
                },
            )
            print(f"{session_id}: 已更新为 cancelled")


async def main(session_ids: list[str]) -> None:
    """执行修复并释放脚本进程创建的数据库连接池。"""
    try:
        await repair_sessions(session_ids)
    finally:
        await engine.dispose()


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
    asyncio.run(main(args.session_ids))
