#!/usr/bin/env python3
"""
Exportera rider_image_data (base64 i Postgres) till filer under static/riders/portraits/.

Varför: Flask slipper avkoda blobs i RAM — webbläsaren hämtar vanliga bildfiler.

Kör från projektroten:

  python tools/export_db_portraits_to_files.py --dry-run
  python tools/export_db_portraits_to_files.py
  python tools/export_db_portraits_to_files.py --clear-blobs

Kräver DATABASE_URL eller PRODUCTION_DATABASE_URL i .env.
Skriver filer lokalt + uppdaterar databasen du pekar mot.

Efter export:
  git add static/riders/portraits
  git commit -m "Add exported rider portrait files"
  git push
(Render måste få filerna via git — disken på servern är inte permanent.)
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import os
import sys
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

DEST_DIR = ROOT / "static" / "riders" / "portraits"
IMAGE_URL_PREFIX = "riders/portraits"


def _ensure_db_url() -> None:
    url = (os.getenv("DATABASE_URL") or "").strip()
    prod = (os.getenv("PRODUCTION_DATABASE_URL") or "").strip()
    if not url and prod:
        os.environ["DATABASE_URL"] = prod
        url = prod
    if url and "postgres" in url and "sslmode=" not in url:
        os.environ["DATABASE_URL"] = url + ("&" if "?" in url else "?") + "sslmode=require"


def _decode_data_url(data_url: str) -> tuple[bytes, str]:
    meta, b64part = data_url.split(",", 1)
    mime = "image/jpeg"
    if ";" in meta:
        mime = meta[5:].split(";")[0].strip() or mime
    return base64.b64decode(b64part), mime


def _to_webp(raw: bytes) -> bytes:
    from PIL import Image

    im = Image.open(BytesIO(raw))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
    else:
        im = im.convert("RGB")
    out = BytesIO()
    im.save(out, format="WEBP", quality=85, method=4)
    return out.getvalue()


def export_portraits(
    *,
    dry_run: bool = False,
    clear_blobs: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    _ensure_db_url()
    from app import create_app
    from models import Rider, db

    app = create_app()
    stats = {
        "candidates": 0,
        "exported": 0,
        "skipped_existing_url": 0,
        "skipped_no_blob": 0,
        "files_written": 0,
        "blobs_cleared": 0,
        "errors": 0,
    }
    file_cache: dict[str, str] = {}

    with app.app_context():
        q = (
            db.session.query(Rider)
            .filter(
                Rider.rider_image_data.isnot(None),
                Rider.rider_image_data != "",
                Rider.rider_image_data.like("data:image%"),
            )
            .order_by(Rider.id)
        )
        if limit:
            q = q.limit(int(limit))
        riders = q.all()
        stats["candidates"] = len(riders)

        if not dry_run:
            DEST_DIR.mkdir(parents=True, exist_ok=True)

        for rider in riders:
            raw_s = str(rider.rider_image_data or "").strip()
            if not raw_s.startswith("data:image"):
                stats["skipped_no_blob"] += 1
                continue

            existing = (rider.image_url or "").strip()
            if existing.startswith(f"{IMAGE_URL_PREFIX}/") and not existing.startswith("http"):
                rel_path = ROOT / "static" / existing.replace("/", os.sep)
                if rel_path.is_file():
                    stats["skipped_existing_url"] += 1
                    if clear_blobs and rider.rider_image_data:
                        if not dry_run:
                            rider.rider_image_data = None
                            stats["blobs_cleared"] += 1
                    continue

            try:
                blob, _mime = _decode_data_url(raw_s)
                digest = hashlib.sha1(blob).hexdigest()[:20]
                if digest in file_cache:
                    rel_url = file_cache[digest]
                else:
                    fname = f"{digest}.webp"
                    rel_url = f"{IMAGE_URL_PREFIX}/{fname}"
                    dest = DEST_DIR / fname
                    if not dry_run:
                        if not dest.is_file():
                            dest.write_bytes(_to_webp(blob))
                            stats["files_written"] += 1
                    else:
                        stats["files_written"] += int(not dest.is_file())
                    file_cache[digest] = rel_url

                label = f"#{rider.rider_number} {rider.name} (id={rider.id})"
                print(f"[OK] {label} -> {rel_url}")

                if not dry_run:
                    rider.image_url = rel_url
                    if clear_blobs:
                        rider.rider_image_data = None
                        stats["blobs_cleared"] += 1
                stats["exported"] += 1
            except Exception as exc:
                stats["errors"] += 1
                print(f"[ERR] id={rider.id} {rider.name}: {exc}")

        if not dry_run:
            db.session.commit()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Export DB rider portraits to static files.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Visa vad som skulle göras utan att skriva filer eller DB.",
    )
    parser.add_argument(
        "--clear-blobs",
        action="store_true",
        help="Sätt rider_image_data=NULL efter lyckad export (minskar DB-storlek + RAM).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max antal förare (test).")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Använd PRODUCTION_DATABASE_URL (Render) istället för lokal DATABASE_URL.",
    )
    args = parser.parse_args()

    if args.production:
        prod = (os.getenv("PRODUCTION_DATABASE_URL") or "").strip()
        if not prod:
            print("ERROR: PRODUCTION_DATABASE_URL saknas i .env")
            sys.exit(1)
        os.environ["DATABASE_URL"] = prod

    db_target = (os.getenv("DATABASE_URL") or "")[:60]
    print(f"DATABASE_URL: {db_target}...")
    print(f"Output: {DEST_DIR}")
    if args.dry_run:
        print("DRY RUN — inga filer eller DB-ändringar sparas.\n")

    stats = export_portraits(
        dry_run=args.dry_run,
        clear_blobs=args.clear_blobs,
        limit=args.limit,
    )

    print("\n--- Summary ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    if not args.dry_run and stats["exported"]:
        print("\nNästa steg:")
        print("  git add static/riders/portraits")
        print("  git commit -m \"Add exported rider portrait files\"")
        print("  git push")


if __name__ == "__main__":
    main()
