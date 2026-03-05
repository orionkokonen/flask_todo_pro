"""簡易レート制限モジュール（プロセス内メモリ版）。

レート制限とは「短時間に大量のリクエストを送る攻撃（ブルートフォース）」を防ぐ仕組み。
Redis などの外部サービスを使わず、Python の標準ライブラリだけで実装している。

仕組み: スライディングウィンドウ方式
  → 「直近 N 秒間に M 回まで」というルールで、制限を超えた IP を一時的にブロックする。
  → 固定ウィンドウと違い、境界をまたいだバースト攻撃にも対応できる。

制約: メモリ上にデータを持つため、複数プロセス間で共有できない。
  シングルプロセス構成（ポートフォリオ用途）なら十分だが、
  本番環境では Redis ベースの Flask-Limiter 等への移行を推奨。
"""
from __future__ import annotations

from collections import deque  # deque＝両端キュー。先頭・末尾どちらからも高速に追加・削除できるリスト
from math import ceil
from threading import Lock
from time import monotonic  # monotonic＝経過時間の単調増加タイマー。システム時刻の巻き戻しに影響されない


class SimpleRateLimiter:
    """スライディングウィンドウ方式のレート制限クラス。

    バケット（"login:192.168.1.1" のような文字列キー）ごとに
    リクエストのタイムスタンプを deque で記録し、制限超過を判定する。
    """

    def __init__(self) -> None:
        self._entries: dict[str, deque[float]] = {}
        # マルチスレッド環境（本番の Gunicorn 等）でデータ競合を防ぐための排他ロック
        self._lock = Lock()

    def _prune(self, bucket: str, now: float, window_seconds: int) -> deque[float] | None:
        """ウィンドウ外（期限切れ）の古い記録を先頭から削除し、残りを返す。

        deque の先頭が最も古いので、順に消すだけで O(k) と軽量。
        全件削除されたバケットは None を返し、呼び出し元でメモリを解放する。
        """
        entries = self._entries.get(bucket)
        if entries is None:
            return None
        cutoff = now - window_seconds
        while entries and entries[0] <= cutoff:
            entries.popleft()
        return entries

    def check(self, bucket: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """制限内かどうかを判定する（記録はしない）。

        記録を分離することで「認証失敗のときだけカウント」等の柔軟な制御が可能。

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
        """失敗したリクエストを現在時刻で記録する。

        認証失敗やバリデーションエラーなど、実際に失敗した場合のみ呼ぶ。
        成功した操作や GET リクエストはカウントしない設計。
        """
        with self._lock:
            now = monotonic()
            entries = self._prune(bucket, now, window_seconds)
            if entries is None:
                entries = self._entries.setdefault(bucket, deque())
            entries.append(now)

    def reset(self, bucket: str) -> None:
        """バケットのカウンターをリセットする（認証成功時に呼ぶ）。

        過去の失敗カウントが残ると、正規ユーザーまでブロックされてしまうため。
        """
        with self._lock:
            self._entries.pop(bucket, None)

    def clear(self) -> None:
        """全バケットをクリアする。テスト間の状態リセット用。"""
        with self._lock:
            self._entries.clear()


# モジュールレベルのシングルトン。
# インスタンスが複数あるとカウントが分散して制限が効かなくなるため、1つだけ生成する。
auth_rate_limiter = SimpleRateLimiter()
