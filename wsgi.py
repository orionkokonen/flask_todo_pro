# このファイルは本番サーバーから Flask アプリを読み込む入口です。
"""本番環境(Render / gunicorn)向けのWSGIエントリポイント。

実行方法:
    gunicorn wsgi:app

アプリ設定やSECRET_KEYの検証は create_app 側に集約し、
このファイルは「本番で読み込まれる入口」であることに責務を限定する。
"""

from app import create_app

# create_app() に設定読込と安全確認を集約し、
# gunicorn 側は「この app を呼ぶだけ」で済む入口にしている。
app = create_app()
