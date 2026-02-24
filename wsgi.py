"""WSGI entrypoint for production (Render / gunicorn).

Run:
    gunicorn wsgi:app
"""

from app import create_app

app = create_app()
