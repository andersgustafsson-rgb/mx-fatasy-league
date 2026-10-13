"""Hämta MXGP-förarbio från mxgp.com och spara i lokal databas.

Usage:
  python tools/sync_mxgp_rider_bios.py
  python tools/sync_mxgp_rider_bios.py --limit 5 --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///fantasy_mx_local.db")
os.environ.pop("RENDER", None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync MXGP rider bios from mxgp.com")
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from app import create_app
    from mxgp_fantasy import ensure_mxgp_2026_roster
    from mxgp_rider_bio import fetch_mxgp_rider_profile, iter_mxgp_riders_needing_bio
    from models import db

    app = create_app()
    with app.app_context():
        ensure_mxgp_2026_roster()
        db.session.commit()
        riders = iter_mxgp_riders_needing_bio(limit=args.limit)
        print(f"Riders to fetch: {len(riders)}")
        ok = 0
        for r in riders:
            profile = fetch_mxgp_rider_profile(r.name or "")
            if not profile.get("ok"):
                print(f"  [skip] {r.name}: {profile.get('error')}")
                continue
            print(f"  [ok] {r.name} <- {profile.get('source_url')}")
            if not args.dry_run:
                from mxgp_rider_bio import apply_mxgp_profile_to_rider

                apply_mxgp_profile_to_rider(r, profile)
                db.session.commit()
            ok += 1
        print(f"Done: {ok}/{len(riders)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
