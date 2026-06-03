"""Ensure a known local dev login exists (test / password)."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///fantasy_mx_local.db")
os.environ.pop("RENDER", None)

from werkzeug.security import generate_password_hash  # noqa: E402

from main import User, app, db  # noqa: E402

USERNAME = "test"
PASSWORD = "password"


def main() -> int:
    with app.app_context():
        user = User.query.filter_by(username=USERNAME).first()
        if not user:
            user = User(
                username=USERNAME,
                password_hash=generate_password_hash(PASSWORD),
                email="test@local.dev",
                is_admin=True,
            )
            db.session.add(user)
            action = "skapad"
        else:
            user.password_hash = generate_password_hash(PASSWORD)
            user.is_admin = True
            if not user.email:
                user.email = "test@local.dev"
            action = "uppdaterad"
        db.session.commit()
        print(f"Lokal inloggning ({action}): {USERNAME} / {PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
