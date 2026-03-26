"""ローカル開発専用のエントリポイント。

本番（Render）は wsgi.py を使い、SECRET_KEY は環境変数で必ず注入する。
このファイルは「SECRET_KEY がなくても起動できる開発環境向け」として分離しており、
本番コードには影響しない。
"""
import os

# 開発専用のフォールバック。環境変数が未設定の場合のみ補完する。
# wsgi.py は SECRET_KEY 未設定時に RuntimeError で起動を止める設計のため、
# この値が本番で使われることはない。
os.environ.setdefault("SECRET_KEY", "dev_secret_key_change_me")

from app import create_app

app = create_app({"DEBUG": True})

if __name__ == "__main__":
    # debug=True でコード変更時の自動リロードとブラウザへのスタックトレース表示を有効にする。
    # 本番では必ず False にする。
    app.run(debug=True)
