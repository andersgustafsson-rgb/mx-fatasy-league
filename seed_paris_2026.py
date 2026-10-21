"""Seed Paris Supercross 2026 (lördag + söndag). Run: py -3 seed_paris_2026.py"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///fantasy_mx_local.db")
os.environ.pop("RENDER", None)

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from paris_fantasy import ensure_paris_2026  # noqa: E402

app = create_app()


def main() -> None:
    with app.app_context():
        info = ensure_paris_2026()
        print("Paris 2026 seed OK:", info)


if __name__ == "__main__":
    main()
