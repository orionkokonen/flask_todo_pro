"""簡易レート制限モジュール（プロセス内メモリ版）。

レート制限とは「短時間に大量のリクエストを送る攻撃（総当たり＝ブルートフォース）」を防ぐ仕組み。
Redis などの外部サービスを使わず、Python の標準ライブラリだけで実装している。

仕組み: スライディングウィンドウ（滑る時間枠）方式
  → 「直近 N 秒間に M 回まで」というルールで、超えた IP を一時ブロックする。
  → 固定ウィンドウ（例: 毎分0秒リセット）と違い、境界をまたいだ集中攻撃にも対応できる。

制約: メモリ上にデータを持つため、複数プロセス（サーバーを複数台起動する構成）では共有できない。
  学習・ポートフォリオ用途なら十分だが、本番では Redis ベースの Flask-Limiter 等を推奨。
"""
from __future__ import annotations

from collections import deque  # 両端キュー。先頭・末尾どちらからも高速に追加・削除できるリスト
from math import ceil
from threading import Lock  # 複数スレッドが同時に同じデータを触るのを防ぐ鍵
from time import monotonic  # OS 稼働時間ベースのタイマー。時刻変更やNTP同期の影響を受けない


class SimpleRateLimiter:
    """スライディングウィンドウ方式のレート制限クラス。

    バケット（"login:192.168.1.1" のような「操作名:IP」のキー）ごとに
    リクエスト時刻を deque に記録し、制限超過を判定する。
    """

    def __init__(self) -> None:
        self._entries: dict[str, deque[float]] = {}
        # 複数リクエストが同時に来ても _entries を壊さないための排他ロック
        self._lock = Lock()

    def _prune(self, bucket: str, now: float, window_seconds: int) -> deque[float] | None:
        """時間枠外（期限切れ）の古い記録を先頭から削除し、残りを返す。

        deque は時系列順なので先頭から消すだけで済む。
        全件消えたバケットは None を返し、呼び出し元でメモリを解放する。
        """
        entries = self._entries.get(bucket)
        if entries is None:
            return None
        cutoff = now - window_seconds
        while entries and entries[0] <= cutoff:
            entries.popleft()
        if not entries:
            self._entries.pop(bucket, None)
            return None
        return entries

    def check(self, bucket: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """制限内かどうかを判定する（この時点ではカウントしない）。

        判定と記録を分離することで「失敗時だけカウント」といった柔軟な使い方ができる。

        Returns:
            (True, 0)          — まだ許可できる
            (False, retry_sec) — ブロック中。retry_sec 秒後に再試行可能
        """
        with self._lock:
            now = monotonic()
            entries = self._prune(bucket, now, window_seconds)
            if not entries:
                self._entries.pop(bucket, None)
                return True, 0
            if len(entries) < limit:
                return True, 0

            # 最古の記録がウィンドウから外れるまでの残り秒数を計算
            retry_after = max(1, ceil(window_seconds - (now - entries[0])))
            return False, retry_after

    def record_failure(self, bucket: str, window_seconds: int) -> None:
        """失敗を現在時刻で記録する。成功時は呼ばない。

        ログイン失敗など「攻撃の可能性がある操作」だけカウントし、
        正常利用まで巻き込まないようにする。
        """
        with self._lock:
            now = monotonic()
            entries = self._prune(bucket, now, window_seconds)
            if entries is None:
                entries = self._entries.setdefault(bucket, deque())
            entries.append(now)

    def reset(self, bucket: str) -> None:
        """認証成功時にカウンターをリセットする。

        過去の失敗回数が残ったままだと、正規ユーザーまでブロックされてしまうため。
        """
        with self._lock:
            self._entries.pop(bucket, None)

    def clear(self) -> None:
        """全バケットをクリアする。テスト間の状態リセット用。"""
        with self._lock:
            self._entries.clear()


# シングルトン（＝アプリ全体で1つだけのインスタンス）。
# 複数作るとカウントが分散して制限が正しく効かなくなる。
auth_rate_limiter = SimpleRateLimiter()
