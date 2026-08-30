"""Generate SMX 2026 seeding posters into static/posters/."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    # Prefer production URL if set so rider numbers match live DB
    prod = os.getenv("PRODUCTION_DATABASE_URL")
    if prod:
        os.environ["DATABASE_URL"] = prod

    from main import app
    from smx_seed_poster_service import save_smx_seed_posters

    with app.app_context():
        paths = save_smx_seed_posters()
        for key, path in paths.items():
            print(f"{key}: {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
