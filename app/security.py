from __future__ import annotations

from collections import deque
from math import ceil
from threading import Lock
from time import monotonic


class SimpleRateLimiter:
    """プロセス内メモリだけで動く簡易レート制限器。"""

    def __init__(self) -> None:
        self._entries: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _prune(self, bucket: str, now: float, window_seconds: int) -> deque[float]:
        entries = self._entries.setdefault(bucket, deque())
        cutoff = now - window_seconds
        while entries and entries[0] <= cutoff:
            entries.popleft()
        if not entries:
            self._entries.pop(bucket, None)
            entries = deque()
        return entries

    def check(self, bucket: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """指定バケットの試行がまだ許可されるかを返す。"""
        with self._lock:
            now = monotonic()
            entries = self._prune(bucket, now, window_seconds)
            if len(entries) < limit:
                return True, 0

            retry_after = max(1, ceil(window_seconds - (now - entries[0])))
            return False, retry_after

    def record_failure(self, bucket: str, window_seconds: int) -> None:
        """失敗試行を記録する。"""
        with self._lock:
            now = monotonic()
            entries = self._prune(bucket, now, window_seconds)
            entries.append(now)
            self._entries[bucket] = entries

    def reset(self, bucket: str) -> None:
        """成功時に試行履歴をリセットする。"""
        with self._lock:
            self._entries.pop(bucket, None)

    def clear(self) -> None:
        """テスト用に全状態をクリアする。"""
        with self._lock:
            self._entries.clear()


auth_rate_limiter = SimpleRateLimiter()
