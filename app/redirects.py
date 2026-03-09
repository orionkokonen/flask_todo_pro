"""安全なリダイレクト先を扱う小さな共通関数。

ログイン後や更新後に別ページへ移動するとき、
送信データや Referer ヘッダーをそのまま信じると
外部サイトへ飛ばされる危険がある。

このファイルでは「自分のサイト内なら移動してよい」
という最低限のルールを 1 か所にまとめる。
"""
from __future__ import annotations

from urllib.parse import urljoin, urlparse

from flask import request


def is_safe_redirect_target(target: str) -> bool:
    """移動先がこのサイト内の http(s) URL かを判定する。

    Open Redirect（外部サイトへ飛ばす攻撃）を防ぐため、
    スキームが http / https で、かつホスト名が今のアプリと同じものだけ許可する。
    """
    ref_url = urlparse(request.host_url)
    # /todo のような相対パスも比較できるよう、いったん絶対 URL にそろえる。
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def safe_redirect_target(target: str | None, fallback: str) -> str:
    """安全ならその URL を返し、危険または空なら代わりの URL を返す。

    呼び出し元は「許可判定」と「だめだった時の戻り先」を分けて考えなくてよくなる。
    """
    if target and is_safe_redirect_target(target):
        return target
    return fallback


def safe_referrer_or(fallback: str) -> str:
    """直前ページへ戻したい時に使う。

    request.referrer はブラウザが送ってくる「直前のページ」だが、
    外部サイトの URL が入ることもある。
    そのため、安全確認を通った時だけ使い、そうでなければ fallback へ戻す。
    """
    return safe_redirect_target(request.referrer, fallback)
