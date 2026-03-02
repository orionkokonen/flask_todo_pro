"""プロセス内メモリを使った簡易レート制限の実装。

Redis などの外部ストアを追加せず、標準ライブラリだけで動かすことで
依存を増やさずに認証系エンドポイントへのブルートフォース対策を実現している。
スライディングウィンドウ方式を採用しており、「直近 N 秒以内に M 回を超えた
クライアント IP を一時ブロック」できる。

制約: in-memory 実装のためプロセスをまたいだカウントの共有はできない。
Gunicorn のマルチワーカー構成や将来のスケールアウトでは各プロセスが独立して
カウントするため、厳密な全体制限にはならない。
ポートフォリオ用途のシングルプロセス構成には十分な抑止力になる。
本番で厳密運用するなら Redis 連携の Flask-Limiter 等に移行すること。
"""
from __future__ import annotations

from collections import deque
from math import ceil
from threading import Lock
from time import monotonic


class SimpleRateLimiter:
    """スライディングウィンドウ方式のプロセス内レート制限器。

    内部状態は dict[bucket_name -> deque[timestamp]] で管理する。
    バケット名は「アクション種別:クライアント IP」の文字列（例: "login:1.2.3.4"）。
    マルチスレッド環境でも競合が起きないよう、状態変更はすべて Lock で排他制御している。
    """

    def __init__(self) -> None:
        self._entries: dict[str, deque[float]] = {}
        # スレッドセーフのため全操作を Lock で保護する。
        # Flask の開発サーバーはシングルスレッドだが、本番（Gunicorn）はマルチスレッドになりうる。
        self._lock = Lock()

    def _prune(self, bucket: str, now: float, window_seconds: int) -> deque[float] | None:
        """ウィンドウ外の古い記録を除去し、現在のウィンドウ内の記録のみを返す。

        deque の先頭（最も古いタイムスタンプ）から順に期限切れを削除するため、
        追い出し件数 k に対して O(k) で完結し、メモリが無限に膨らまない。
        ウィンドウ内の記録がゼロになったバケットはメモリ節約のため dict から削除する。
        """
        entries = self._entries.get(bucket)
        if entries is None:
            return None
        cutoff = now - window_seconds
        while entries and entries[0] <= cutoff:
            entries.popleft()
        return entries

    def check(self, bucket: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """指定バケットの試行がまだ許可されるかを確認する。

        このメソッドはチェックのみを行い、失敗記録はしない。
        失敗記録は record_failure() を別途呼ぶ設計にすることで、
        「バリデーションエラーの場合だけ記録する」などの細かい制御が可能になる。

        Returns:
            (True, 0)          - まだ許可できる
            (False, retry_sec) - ブロック中。retry_sec 秒後に再試行可能。
        """
        with self._lock:
            now = monotonic()
            # check() はリクエストを通してよいかを判断するだけで、失敗の記録はしない。
            entries = self._prune(bucket, now, window_seconds)
            if not entries:
                self._entries.pop(bucket, None)
                return True, 0
            if len(entries) < limit:
                return True, 0

            # 最も古い記録がウィンドウを抜けるまでの秒数を待機時間として返す。
            retry_after = max(1, ceil(window_seconds - (now - entries[0])))
            return False, retry_after

    def record_failure(self, bucket: str, window_seconds: int) -> None:
        """失敗試行を現在時刻として記録する。

        check() とは分離した設計にしており、認証失敗・バリデーションエラーなど
        「処理が完了しなかった POST」のときだけ呼ぶことで、正規の GET リクエストや
        成功した操作がカウントに影響しないようにしている。
        """
        with self._lock:
            now = monotonic()
            # record_failure() は POST 試行が実際に失敗したときだけ呼ぶ。
            entries = self._prune(bucket, now, window_seconds)
            if entries is None:
                entries = self._entries.setdefault(bucket, deque())
            entries.append(now)

    def reset(self, bucket: str) -> None:
        """認証成功時にそのバケットのカウンターをリセットする。

        ログイン成功後もカウントが残ったままだと、過去の失敗によって
        正規ユーザーが引き続きブロックされる誤検知が起きる。
        成功時にリセットすることでこれを防ぐ。
        """
        with self._lock:
            self._entries.pop(bucket, None)

    def clear(self) -> None:
        """全バケットの状態をクリアする。テスト間の独立性を保つために使用する。"""
        with self._lock:
            self._entries.clear()


# アプリ全体で共有するシングルトンインスタンス。
# インスタンスが複数存在するとバケットが分断されレート制限が機能しなくなるため、
# モジュールレベルで 1 つだけ生成し、各ビューはこれをインポートして使う。
auth_rate_limiter = SimpleRateLimiter()
