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
from racerx_rider_bio import (  # noqa: E402
    _normalize_rider_lookup_name,
    copy_bio_between_riders,
    find_rider_with_bio_by_name,
    sync_portraits_for_name,
    sync_rider_twins,
)
from tools.apply_racerx_bio import _make_app  # noqa: E402


def main() -> None:
    app = _make_app()
    with app.app_context():
        all_riders = Rider.query.all()
        keys = sorted({_normalize_rider_lookup_name(r.name or "") for r in all_riders} - {""})
        bio_fixed = 0
        portrait_fixed = 0
        for key in keys:
            source = find_rider_with_bio_by_name(key, riders=all_riders)
            if source:
                for rider in all_riders:
                    if _normalize_rider_lookup_name(rider.name or "") != key:
                        continue
                    if rider.id == source.id or (rider.bio or "").strip():
                        continue
                    if copy_bio_between_riders(source, rider):
                        bio_fixed += 1
                sync_rider_twins(source, riders=all_riders)
            synced_img = sync_portraits_for_name(
                next(r.name for r in all_riders if _normalize_rider_lookup_name(r.name or "") == key),
                riders=all_riders,
            )
            portrait_fixed += len(synced_img)
        db.session.commit()
        print(f"Synced bio to {bio_fixed} rader, porträtt till {portrait_fixed} rader")


if __name__ == "__main__":
    main()
