# このファイルは本番環境でアプリをどう起動するかを書くファイルです。
web: python -m flask --app wsgi.py db upgrade && gunicorn wsgi:app
