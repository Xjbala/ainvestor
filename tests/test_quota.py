# -*- coding: utf-8 -*-
"""配额计量与订阅闸门单元测试。

用 in-memory SQLite 跑真实 ORM，覆盖：
  - 匿名用户滚动 30 天窗口
  - 登录无订阅 → free plan 月度额度
  - 订阅 active → grant 窗口语义
  - 超额抛 402（匿名）/ 429（登录）
  - 配额迁移（匿名 → 注册用户）
"""

import asyncio
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.core.dependencies import get_anonymous_or_user  # noqa: F401  (import-side effect)
from backend.core.quota import (
    ANON_AI_ANALYSIS_QUOTA,
    ANON_EXPERT_QUOTA,
    ANON_WINDOW_DAYS,
    Identity,
    check_and_consume,
    get_entitlements,
    hash_anonymous_key,
    migrate_anonymous_usage,
    resolve_quota_window,
)
from backend.persistence.db import Base
from backend.persistence.orm_models import (
    Plan,
    QuotaGrant,
    QuotaResource,
    Subscription,
    SubscriptionStatus,
    UsageEvent,
    User,
    UserRole,
)


async def _setup_db():
    """初始化 in-memory SQLite + seed plans/user。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with Session() as s:
        # 三个计划
        s.add_all([
            Plan(code="free", name="免费版", ai_quota_monthly=3, expert_quota_monthly=10, data_api_quota_monthly=0, price_cents=0, is_active=True, sort_order=0),
            Plan(code="pro", name="专业版", ai_quota_monthly=50, expert_quota_monthly=200, data_api_quota_monthly=1000, price_cents=9900, is_active=True, sort_order=10),
        ])
        # 一个登录用户（无订阅）
        s.add(User(id="u1", username="alice", email="a@x.com", hashed_password="x", role=UserRole.USER, is_active=True))
        # 一个登录用户（有 pro 订阅）
        s.add(User(id="u2", username="bob", email="b@x.com", hashed_password="x", role=UserRole.USER, is_active=True))
        await s.commit()

        now = datetime.utcnow()
        # bob 的订阅 + grant（窗口覆盖 now）
        sub = Subscription(
            id="s1", user_id="u2", plan_code="pro", status=SubscriptionStatus.ACTIVE,
            current_period_start=now - timedelta(days=5),
            current_period_end=now + timedelta(days=25),
        )
        grant = QuotaGrant(
            id="g1", user_id="u2", plan_code="pro",
            period_start=now - timedelta(days=5),
            period_end=now + timedelta(days=25),
            ai_quota=50, expert_quota=200, data_api_quota=1000,
            source_subscription_id="s1",
        )
        s.add_all([sub, grant])
        await s.commit()

    return engine, Session


class TestQuotaWindow(unittest.TestCase):
    def test_anonymous_uses_rolling_30d_window(self):
        async def run():
            engine, Session = await _setup_db()
            ident = Identity(user_id=None, anonymous_key="anon-abc", ip_hash=None)
            async with Session() as s:
                w = await resolve_quota_window(s, ident, QuotaResource.AI_ANALYSIS)
            self.assertEqual(w.quota_limit, ANON_AI_ANALYSIS_QUOTA)
            self.assertEqual(w.plan_code, "free")
            # 窗口长度 = ANON_WINDOW_DAYS
            delta = w.window_end - w.window_start
            self.assertAlmostEqual(delta.total_seconds(), ANON_WINDOW_DAYS * 86400, delta=5)
            await engine.dispose()
        asyncio.run(run())

    def test_logged_in_no_subscription_uses_free_plan(self):
        async def run():
            engine, Session = await _setup_db()
            ident = Identity(user_id="u1", anonymous_key=None, ip_hash=None)
            async with Session() as s:
                w = await resolve_quota_window(s, ident, QuotaResource.EXPERT_VALUATION)
            self.assertEqual(w.quota_limit, 10)  # free.expert_quota_monthly
            self.assertEqual(w.plan_code, "free")
            await engine.dispose()
        asyncio.run(run())

    def test_active_subscription_uses_grant_window(self):
        async def run():
            engine, Session = await _setup_db()
            ident = Identity(user_id="u2", anonymous_key=None, ip_hash=None)
            async with Session() as s:
                w = await resolve_quota_window(s, ident, QuotaResource.AI_ANALYSIS)
            self.assertEqual(w.quota_limit, 50)  # pro.ai_quota_monthly via grant
            self.assertEqual(w.plan_code, "pro")
            await engine.dispose()
        asyncio.run(run())


class TestCheckAndConsume(unittest.TestCase):
    def test_consume_within_anon_quota(self):
        async def run():
            engine, Session = await _setup_db()
            ident = Identity(user_id=None, anonymous_key="anon-1", ip_hash=None)
            async with Session() as s:
                used, quota, _ = await check_and_consume(s, ident, QuotaResource.AI_ANALYSIS)
            self.assertEqual(used, 1)
            self.assertEqual(quota, ANON_AI_ANALYSIS_QUOTA)
            await engine.dispose()
        asyncio.run(run())

    def test_anonymous_over_quota_raises_402(self):
        async def run():
            engine, Session = await _setup_db()
            ident = Identity(user_id=None, anonymous_key="anon-2", ip_hash=None)
            from fastapi import HTTPException
            async with Session() as s:
                # ANON_AI_ANALYSIS_QUOTA 默认 1，第一次扣成功，第二次应抛 402
                await check_and_consume(s, ident, QuotaResource.AI_ANALYSIS)
                with self.assertRaises(HTTPException) as ctx:
                    await check_and_consume(s, ident, QuotaResource.AI_ANALYSIS)
            self.assertEqual(ctx.exception.status_code, 402)
            await engine.dispose()
        asyncio.run(run())

    def test_logged_in_over_quota_raises_429(self):
        async def run():
            engine, Session = await _setup_db()
            # u1 free plan ai=3。用 4 次应抛 429。
            ident = Identity(user_id="u1", anonymous_key=None, ip_hash=None)
            from fastapi import HTTPException
            async with Session() as s:
                for _ in range(3):
                    await check_and_consume(s, ident, QuotaResource.AI_ANALYSIS)
                with self.assertRaises(HTTPException) as ctx:
                    await check_and_consume(s, ident, QuotaResource.AI_ANALYSIS)
            self.assertEqual(ctx.exception.status_code, 429)
            await engine.dispose()
        asyncio.run(run())

    def test_pro_user_high_quota(self):
        async def run():
            engine, Session = await _setup_db()
            ident = Identity(user_id="u2", anonymous_key=None, ip_hash=None)
            async with Session() as s:
                # pro.ai=50，连扣 3 次都应成功
                for i in range(3):
                    used, quota, _ = await check_and_consume(s, ident, QuotaResource.AI_ANALYSIS)
                    self.assertEqual(used, i + 1)
                self.assertEqual(quota, 50)
            await engine.dispose()
        asyncio.run(run())


class TestQuotaMigration(unittest.TestCase):
    def test_migrate_anonymous_to_user(self):
        async def run():
            engine, Session = await _setup_db()
            anon_key = hash_anonymous_key("raw-uuid-1")
            ident_anon = Identity(user_id=None, anonymous_key=anon_key, ip_hash=None)
            async with Session() as s:
                await check_and_consume(s, ident_anon, QuotaResource.AI_ANALYSIS)
                await s.commit()

            # 注册新用户，迁移
            async with Session() as s:
                s.add(User(id="u3", username="carol", email="c@x.com", hashed_password="x", role=UserRole.USER, is_active=True))
                await s.commit()
                migrated = await migrate_anonymous_usage(s, anon_key, "u3")
                await s.commit()
            self.assertEqual(migrated, 1)

            # 迁移后 u3 的 usage 应计入其 user_id
            ident_user = Identity(user_id="u3", anonymous_key=None, ip_hash=None)
            async with Session() as s:
                ents = await get_entitlements(s, ident_user)
            self.assertEqual(ents["entitlements"]["ai_analysis"]["used"], 1)
            await engine.dispose()
        asyncio.run(run())


class TestEntitlements(unittest.TestCase):
    def test_anonymous_entitlements_shape(self):
        async def run():
            engine, Session = await _setup_db()
            ident = Identity(user_id=None, anonymous_key="anon-ent", ip_hash=None)
            async with Session() as s:
                ents = await get_entitlements(s, ident)
            self.assertTrue(ents["is_anonymous"])
            self.assertEqual(ents["plan_code"], "free")
            self.assertIsNone(ents["subscription"])
            self.assertIn("ai_analysis", ents["entitlements"])
            self.assertIn("expert_valuation", ents["entitlements"])
            self.assertEqual(ents["entitlements"]["ai_analysis"]["remaining"], ANON_AI_ANALYSIS_QUOTA)
            await engine.dispose()
        asyncio.run(run())

    def test_pro_user_entitlements(self):
        async def run():
            engine, Session = await _setup_db()
            ident = Identity(user_id="u2", anonymous_key=None, ip_hash=None)
            async with Session() as s:
                ents = await get_entitlements(s, ident)
            self.assertFalse(ents["is_anonymous"])
            self.assertEqual(ents["subscription"]["plan_code"], "pro")
            self.assertEqual(ents["entitlements"]["ai_analysis"]["remaining"], 50)
            await engine.dispose()
        asyncio.run(run())


class TestHashing(unittest.TestCase):
    def test_hash_anonymous_key_is_deterministic(self):
        h1 = hash_anonymous_key("abc-123")
        h2 = hash_anonymous_key("abc-123")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, "abc-123")

    def test_hash_anonymous_key_idempotent(self):
        h1 = hash_anonymous_key("abc-123")
        # 再次传入已哈希值应原样返回
        h2 = hash_anonymous_key(h1)
        self.assertEqual(h1, h2)


if __name__ == "__main__":
    unittest.main()
