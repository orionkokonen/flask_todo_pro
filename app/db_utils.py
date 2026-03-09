"""DB 書き込み失敗時の共通処理。"""
from __future__ import annotations

from flask import current_app

from app import db


def rollback_session(operation: str) -> None:
    """失敗したトランザクションを巻き戻し、サーバーログへ残す。"""
    db.session.rollback()
    current_app.logger.exception("database write failed: %s", operation)
