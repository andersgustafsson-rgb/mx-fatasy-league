"""Seed WSX 2026 series + competitions (+ optional roster upsert) for local/offline use.

Usage (from repo root, same DB as start_local.bat):
  set DATABASE_URL=sqlite:///fantasy_mx_local.db
  py -3 seed_wsx_2026.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///fantasy_mx_local.db")
os.environ.pop("RENDER", None)

from main import (  # noqa: E402
    app,
    ensure_wsx_2026,
    ensure_wsx_2026_roster,
    sync_wsx_canadian_gp_entry_list,
    sync_wsx_round_only_wildcards,
)


def main() -> int:
    with app.app_context():
        series_info = ensure_wsx_2026(deactivate_2025=True)
        roster_info = ensure_wsx_2026_roster()
        entry_info = sync_wsx_canadian_gp_entry_list()
        wc_info = sync_wsx_round_only_wildcards()
        print("WSX 2026 seed OK")
        print(" series:", series_info)
        print(" roster:", roster_info)
        print(" canadian_gp_entry:", entry_info)
        print(" round_only_wildcards:", wc_info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
