"""本番環境(Render / gunicorn)向けのWSGIエントリポイント。

Run:
    gunicorn wsgi:app

アプリ設定やSECRET_KEYの検証は create_app 側に集約し、
このファイルは「本番で読み込まれる入口」であることに責務を限定する。
"""

from app import create_app

app = create_app()
