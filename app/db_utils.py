"""このファイルは、データベース保存で失敗したときに安全に元へ戻す処理をまとめています。

保存系の route では、commit() が例外で止まったあとに rollback() しないと
「この接続はエラー中」という状態が残り続ける。
放置すると次の保存処理にも影響が出るため、
後片づけをこの 1 か所にまとめている。
"""
from __future__ import annotations

from flask import current_app

from app import db


def rollback_session(operation: str) -> None:
    """書き込み失敗後の後片づけを行う。

    operation には「何の処理で失敗したか」を短く入れる。
    画面には汎用メッセージだけ返し、詳しい原因はログ側で追えるようにする。
    """
    # rollback() は「途中までの変更をなかったことにする」処理。
    # これをしないと、同じ DB セッションで次の保存をしたときに再び失敗しやすい。
    db.session.rollback()
    # logger.exception() は失敗理由とスタックトレース（エラーの発生箇所の一覧）をログに残す。
    # ユーザーへは汎用メッセージだけ返し、詳細はサーバーログ側で確認できるようにする。
    current_app.logger.exception("database write failed: %s", operation)
