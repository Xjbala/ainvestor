# -*- coding: utf-8 -*-
"""
进程内邮箱验证码存储

6 位数字验证码，10 分钟过期。
单 worker 部署，重启丢失可接受（用户重新发送即可）。
"""

import hashlib
import secrets
import time
from threading import Lock
from typing import Optional

CODE_TTL_SECONDS = 10 * 60  # 10 分钟
CODE_LENGTH = 6
MAX_VERIFY_ATTEMPTS = 5


class _Entry:
    __slots__ = ("code_hash", "expires_at", "attempts")

    def __init__(self, code_hash: str, expires_at: float) -> None:
        self.code_hash = code_hash
        self.expires_at = expires_at
        self.attempts = 0


class VerificationCodeStore:
    def __init__(self) -> None:
        self._store: dict[str, _Entry] = {}
        self._lock = Lock()

    @staticmethod
    def _hash(code: str) -> str:
        return hashlib.sha256(code.encode()).hexdigest()

    @staticmethod
    def _generate() -> str:
        return f"{secrets.randbelow(1000000):0{CODE_LENGTH}d}"

    def _purge_expired(self, now: float) -> None:
        expired = [k for k, v in self._store.items() if v.expires_at <= now]
        for k in expired:
            self._store.pop(k, None)

    def issue(self, email: str) -> str:
        """生成并存储验证码，返回明文（由调用方发送邮件）"""
        code = self._generate()
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            self._store[email.lower()] = _Entry(
                self._hash(code), now + CODE_TTL_SECONDS
            )
        return code

    def verify(self, email: str, code: str) -> bool:
        """
        校验验证码。成功后立即删除（一次性）。
        失败累计 attempts，超过 MAX_VERIFY_ATTEMPTS 后删除。
        """
        key = email.lower()
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            entry = self._store.get(key)
            if entry is None:
                return False
            if entry.expires_at <= now:
                self._store.pop(key, None)
                return False
            entry.attempts += 1
            if entry.attempts > MAX_VERIFY_ATTEMPTS:
                self._store.pop(key, None)
                return False
            if entry.code_hash != self._hash(code):
                return False
            self._store.pop(key, None)
            return True

    def has_pending(self, email: str) -> bool:
        key = email.lower()
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            entry = self._store.get(key)
            return entry is not None and entry.expires_at > now


verification_code_store = VerificationCodeStore()
