import os

# Development fallback. Production must provide SECRET_KEY explicitly.
os.environ.setdefault("SECRET_KEY", "dev_secret_key_change_me")

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
