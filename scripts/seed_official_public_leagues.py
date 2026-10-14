"""Seed officiella publika ligor + banner-bilder.

  python scripts/seed_official_public_leagues.py           # dry-run (bara bilder)
  python scripts/seed_official_public_leagues.py --apply   # upsert i DB
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Officiella publika ligor")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Skriv ligor till databasen (idempotent)",
    )
    parser.add_argument(
        "--images-only",
        action="store_true",
        help="Generera endast JPEG-banners i static/",
    )
    args = parser.parse_args()

    from services.official_leagues import (
        ensure_official_public_leagues,
        render_official_league_banners,
    )

    paths = render_official_league_banners()
    print(f"Banner-bilder: {len(paths)} filer i static/leagues/official/")

    if args.images_only:
        return 0

    if not args.apply:
        print("Dry-run — lägg till --apply för att skapa/uppdatera ligor i DB.")
        return 0

    from app import create_app

    app = create_app()
    with app.app_context():
        result = ensure_official_public_leagues(render_images=False)
    print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
