# This file exposes the Flask app for production servers.
"""WSGI entry point for production.

Run with:
    gunicorn wsgi:app
"""

from app import create_app

# Gunicorn imports this module-level app object.
app = create_app()
