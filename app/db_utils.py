"""DB への保存が失敗したときの後片づけをまとめる。

保存系の route では、commit() が例外で止まったあとに rollback() しないと
「この接続はエラー中」という状態が残りやすい。
そのままだと次の保存処理まで巻き添えになりやすいので、
後片づけを 1 か所へ寄せて読みやすくしている。
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
    # logger.exception() は失敗理由とスタックトレース（どこで落ちたかの履歴）を残す。
    # 画面には出さず、運用中の調査材料だけサーバー側へ残したいときに向いている。
    current_app.logger.exception("database write failed: %s", operation)
