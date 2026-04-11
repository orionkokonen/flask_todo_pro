"""このファイルは、短時間の連続アクセスを制限して不正利用を防ぐ処理です。

レート制限とは「短時間に大量のリクエストを送る攻撃（総当たり＝ブルートフォース）」を防ぐ仕組み。
Redis などの外部サービスを使わず、Python の標準ライブラリだけで実装している。

仕組み: スライディングウィンドウ（滑る時間枠）方式
  → 「直近 N 秒間に M 回まで」というルールで、超えた IP を一時ブロックする。
  → 固定ウィンドウ（例: 毎分0秒リセット）と違い、境界をまたいだ集中攻撃にも対応できる。

制約: メモリ上にデータを持つため、複数プロセス（サーバーを複数台起動する構成）では共有できない。
  学習・ポートフォリオ用途なら十分だが、本番では Redis ベースの Flask-Limiter 等を推奨。
"""
from __future__ import annotations

from collections import deque  # 両端キュー。先頭・末尾どちらからも高速に追加・削除できる
from math import ceil
from threading import Lock  # 複数スレッドが同時に同じデータを触るのを防ぐ鍵
from time import monotonic  # OS 稼働時間ベースのタイマー。時刻変更や NTP 同期の影響を受けない


class SimpleRateLimiter:
    """スライディングウィンドウ方式のレート制限クラス。

    バケット（"login:192.168.1.1" のような「操作名:IP」のキー）ごとに
    リクエスト時刻を deque に記録し、制限超過を判定する。
    """

    def __init__(self) -> None:
        # `_entries` の形:
        # {"login:127.0.0.1": [失敗時刻, 失敗時刻, ...]}
        # という対応表にしておくと、「誰の何回目か」を素直に追える。
        self._entries: dict[str, deque[float]] = {}
        # 複数リクエストが同時に来ても _entries を壊さないための排他ロック
        self._lock = Lock()

    def _prune(self, bucket: str, now: float, window_seconds: int) -> deque[float] | None:
        """時間枠外（期限切れ）の古い記録を捨てる。

        記録は「古い順」に並んでいるので、先頭から見ればよい。
        使い終わったバケットまで辞書に残すと、アクセスが終わった IP の情報が
        少しずつ溜まってしまうため、空になったらここで片づける。
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
        """ログイン施行時に制限内かどうかを判定する（この時点ではカウントしない）。

        判定と記録を分離することで「失敗時だけカウント」といった柔軟な使い方ができる。

        Returns:
            (True, 0)          — まだ許可できる
            (False, retry_sec) — ブロック中。retry_sec 秒後に再試行可能
        """
        with self._lock:
            now = monotonic()
            entries = self._prune(bucket, now, window_seconds)
            # 空バケットを残さないよう、念のためここでも pop(None) しておく。
            if not entries:
                self._entries.pop(bucket, None)
                return True, 0
            if len(entries) < limit:
                return True, 0

            # 一番古い失敗が時間枠から消えれば、次の試行を許可できる。
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
                # 初回失敗時だけ空の入れ物を作り、以後は同じ deque に時刻を積む。
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
