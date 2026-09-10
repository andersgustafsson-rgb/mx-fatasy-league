"""Seed MXON 2026 (Ernée) series + competition + nations for local/offline use.

Usage (from repo root, same DB as start_local.bat):
  set DATABASE_URL=sqlite:///fantasy_mx_local.db
  py -3 seed_mxon_2026.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///fantasy_mx_local.db")
os.environ.pop("RENDER", None)

from main import app  # noqa: E402
from mxon_fantasy import ensure_mxon_2026  # noqa: E402
from models import db  # noqa: E402


def main() -> int:
    with app.app_context():
        db.create_all()
        info = ensure_mxon_2026(attach_track_image=True)
        print("MXON 2026 seed OK")
        print(" ", info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
