# -*- coding: utf-8 -*-
"""
注册安全相关纯逻辑测试：限流器 + 验证码存储
"""

import unittest

from backend.core.rate_limiter import SlidingWindowRateLimiter
from backend.core.verification_codes import VerificationCodeStore


class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        self.limiter = SlidingWindowRateLimiter()

    def test_allows_within_limit(self):
        ok, rem = self.limiter.consume("ip:1", 3, 60)
        self.assertTrue(ok)
        self.assertEqual(rem, 2)

    def test_blocks_over_limit(self):
        for _ in range(3):
            self.limiter.consume("ip:2", 3, 60)
        ok, rem = self.limiter.consume("ip:2", 3, 60)
        self.assertFalse(ok)
        self.assertEqual(rem, 0)

    def test_different_keys_independent(self):
        for _ in range(3):
            self.limiter.consume("ip:a", 3, 60)
        ok, _ = self.limiter.consume("ip:b", 3, 60)
        self.assertTrue(ok)

    def test_check_does_not_consume(self):
        for _ in range(3):
            self.limiter.consume("ip:3", 3, 60)
        ok, _ = self.limiter.check("ip:3", 3, 60)
        self.assertFalse(ok)
        ok, _ = self.limiter.check("ip:4", 3, 60)
        self.assertTrue(ok)
        ok, rem = self.limiter.check("ip:4", 3, 60)
        self.assertTrue(ok)
        self.assertEqual(rem, 3)


class TestVerificationCodeStore(unittest.TestCase):
    def setUp(self):
        self.store = VerificationCodeStore()

    def test_issue_and_verify(self):
        code = self.store.issue("user@example.com")
        self.assertEqual(len(code), 6)
        self.assertTrue(self.store.verify("user@example.com", code))

    def test_one_time_use(self):
        code = self.store.issue("user@example.com")
        self.assertTrue(self.store.verify("user@example.com", code))
        self.assertFalse(self.store.verify("user@example.com", code))

    def test_wrong_code(self):
        self.store.issue("user@example.com")
        self.assertFalse(self.store.verify("user@example.com", "000000"))

    def test_case_insensitive_email(self):
        code = self.store.issue("User@Example.COM")
        self.assertTrue(self.store.verify("user@example.com", code))

    def test_max_attempts(self):
        self.store.issue("user@example.com")
        for _ in range(5):
            self.assertFalse(self.store.verify("user@example.com", "000000"))
        self.assertFalse(self.store.verify("user@example.com", "000000"))

    def test_has_pending(self):
        self.assertFalse(self.store.has_pending("user@example.com"))
        self.store.issue("user@example.com")
        self.assertTrue(self.store.has_pending("user@example.com"))
        code = self.store.issue("user@example.com")
        self.store.verify("user@example.com", code)
        self.assertFalse(self.store.has_pending("user@example.com"))


if __name__ == "__main__":
    unittest.main()
