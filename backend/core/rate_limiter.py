# -*- coding: utf-8 -*-
"""
进程内滑动窗口限流器

单 worker 部署场景下无需 Redis，用字典 + TTL 即可。
若未来扩展为多 worker，需替换为 Redis 实现。
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List


@dataclass
class _Bucket:
    timestamps: List[float] = field(default_factory=list)


class SlidingWindowRateLimiter:
    """滑动窗口限流器：在 window_seconds 内最多允许 max_requests 次"""

    def __init__(self) -> None:
        self._buckets: Dict[str, _Bucket] = defaultdict(_Bucket)
        self._lock = Lock()

    def _purge(self, key: str, now: float, window: int) -> None:
        bucket = self._buckets.get(key)
        if bucket is None:
            return
        cutoff = now - window
        bucket.timestamps[:] = [t for t in bucket.timestamps if t > cutoff]
        if not bucket.timestamps:
            self._buckets.pop(key, None)

    def check(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """
        检查是否允许请求（不消耗配额）。

        Returns:
            (allowed, remaining) — remaining 为窗口内剩余次数
        """
        now = time.monotonic()
        with self._lock:
            self._purge(key, now, window_seconds)
            bucket = self._buckets[key]
            count = len(bucket.timestamps)
            if count >= max_requests:
                return False, 0
            return True, max_requests - count

    def consume(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """
        消耗一次配额。

        Returns:
            (allowed, remaining) — allowed=False 表示被限流
        """
        now = time.monotonic()
        with self._lock:
            self._purge(key, now, window_seconds)
            bucket = self._buckets[key]
            count = len(bucket.timestamps)
            if count >= max_requests:
                return False, 0
            bucket.timestamps.append(now)
            return True, max_requests - count - 1


rate_limiter = SlidingWindowRateLimiter()
