"""Quick Paris DB + route check. Run: py -3 scripts/_paris_quick_check.py"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from paris_fantasy import ensure_paris_2026, get_paris_weekend


def main() -> None:
    app = create_app()
    with app.app_context():
        print("seed", ensure_paris_2026())
        wk = get_paris_weekend(2026)
        for key in ("saturday", "sunday"):
            c = wk.get(key)
            if not c:
                print(key, "MISSING")
                continue
            print(
                key,
                c.id,
                c.event_date,
                getattr(c, "start_time", None),
                c.series,
                c.phase,
            )
    with app.test_client() as client:
        for path in (
            "/get_paris_leaderboard?year=2026",
            "/race_countdown?mode=real&series=PARIS",
            "/race_countdown?mode=real&series=PARIS&competition_id=156",
            "/admin/api/paris_roster/156",
        ):
            r = client.get(path)
            print(path, "->", r.status_code)


if __name__ == "__main__":
    main()
