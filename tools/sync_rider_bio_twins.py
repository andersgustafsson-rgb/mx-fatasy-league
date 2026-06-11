"""Kopiera bio och porträtt mellan dublett-rader (samma namn, t.ex. 450cc + wsx_sx1)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from models import Rider, db  # noqa: E402
from racerx_rider_bio import sync_all_rider_name_twins  # noqa: E402
from tools.apply_racerx_bio import _make_app  # noqa: E402


def main() -> None:
    app = _make_app()
    with app.app_context():
        stats = sync_all_rider_name_twins()
        db.session.commit()
        print(
            f"Synced bio to {stats['bio_rows_updated']} rader, "
            f"porträtt till {stats['portrait_rows_updated']} rader "
            f"({stats['names_processed']} namn)"
        )


if __name__ == "__main__":
    main()
