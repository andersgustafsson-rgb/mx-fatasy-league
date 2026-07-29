"""Fill missing WSX rider bios: AMA twin copy first, then RacerX fetch.

Usage (writes DB from DATABASE_URL / PRODUCTION_DATABASE_URL):
  set DATABASE_URL=...   # or rely on PRODUCTION_DATABASE_URL
  python tools/fill_wsx_racerx_bios.py
  python tools/fill_wsx_racerx_bios.py --dry-run
  python tools/fill_wsx_racerx_bios.py --translate-sv
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")


def _resolve_uri(prefer_prod: bool) -> str:
    candidates = []
    if prefer_prod:
        candidates.append(os.getenv("PRODUCTION_DATABASE_URL") or "")
    candidates.append(os.getenv("DATABASE_URL") or "")
    for raw in candidates:
        uri = (raw or "").strip()
        if not uri:
            continue
        if uri.startswith("postgres://"):
            uri = "postgresql://" + uri[len("postgres://") :]
        return uri
    raise SystemExit("No DATABASE_URL / PRODUCTION_DATABASE_URL")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill WSX bios from AMA twins + RacerX")
    parser.add_argument("--prod", action="store_true", help="Prefer PRODUCTION_DATABASE_URL")
    parser.add_argument("--delay", type=float, default=0.7)
    parser.add_argument("--translate-sv", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retry-skipped", action="store_true", help="Clear skip and retry 404/no_bio")
    args = parser.parse_args()

    uri = _resolve_uri(prefer_prod=args.prod or bool(os.getenv("PRODUCTION_DATABASE_URL")))
    os.environ["DATABASE_URL"] = uri
    os.environ.pop("RENDER", None)

    from flask import Flask
    from models import Rider, db
    from racerx_rider_bio import (
        apply_profile_to_rider,
        bulk_fill_wsx_from_ama_twins,
        clear_racerx_bio_skip,
        fetch_racerx_rider_profile,
        mark_racerx_bio_skip,
        sync_rider_twins,
    )

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    host = uri.split("@")[-1] if "@" in uri else uri[:48]
    print("DB host/path:", host)

    with app.app_context():
        if args.retry_skipped:
            rows = Rider.query.filter(
                Rider.class_name.in_(("wsx_sx1", "wsx_sx2")),
                Rider.racerx_bio_skip.isnot(None),
                Rider.racerx_bio_skip != "",
            ).all()
            for r in rows:
                if not (r.bio or "").strip():
                    clear_racerx_bio_skip(r)
            if not args.dry_run:
                db.session.commit()
            print(f"Cleared skip on {len(rows)} WSX rows without bio")

        twin_stats = {"wsx_bio_filled": 0, "wsx_portrait_url_filled": 0, "wsx_names_fixed": 0}
        if not args.dry_run:
            twin_stats = bulk_fill_wsx_from_ama_twins()
            db.session.commit()
        print("AMA twin fill:", twin_stats)

        missing = (
            Rider.query.filter(
                Rider.class_name.in_(("wsx_sx1", "wsx_sx2")),
                db.or_(Rider.bio.is_(None), Rider.bio == ""),
            )
            .order_by(Rider.class_name, Rider.name)
            .all()
        )
        # Unique by name: fetch once, apply to primary missing row (sync twins covers rest)
        seen: set[str] = set()
        plan: list[Rider] = []
        for r in missing:
            key = " ".join((r.name or "").strip().lower().split())
            if not key or key in seen:
                continue
            skip = (getattr(r, "racerx_bio_skip", None) or "").strip()
            if skip and not args.retry_skipped:
                print(f"  skip marked: {r.name} ({skip[:60]})")
                continue
            seen.add(key)
            plan.append(r)

        print(f"RacerX fetch plan: {len(plan)} names" + (" (dry-run)" if args.dry_run else ""))
        if args.dry_run:
            for r in plan:
                print(f"  fetch {r.class_name} #{r.rider_number or '-'} {r.name}")
            return

        ok = 0
        fail = 0
        results = []
        for i, rider in enumerate(plan, 1):
            name = (rider.name or "").strip()
            print(f"[{i}/{len(plan)}] {name}...", end=" ", flush=True)
            try:
                profile = fetch_racerx_rider_profile(name)
                if not profile.get("ok"):
                    err = profile.get("error", "?")
                    mark_racerx_bio_skip(rider, err)
                    db.session.commit()
                    print("SKIP", err[:80])
                    fail += 1
                    results.append({"name": name, "ok": False, "error": err})
                    time.sleep(args.delay)
                    continue
                synced = apply_profile_to_rider(rider, profile, sync_twins=True)
                if args.translate_sv and (rider.bio or "").strip():
                    from rider_bio_translate import ensure_swedish_bio

                    ensure_swedish_bio(rider)
                    sync_rider_twins(rider)
                db.session.commit()
                print(f"OK (+{len(synced)} twins) {profile.get('source_url', '')}")
                ok += 1
                results.append({"name": name, "ok": True, "url": profile.get("source_url")})
            except Exception as exc:
                db.session.rollback()
                print("ERR", exc)
                fail += 1
                results.append({"name": name, "ok": False, "error": str(exc)})
            if i < len(plan):
                time.sleep(args.delay)

        still = Rider.query.filter(
            Rider.class_name.in_(("wsx_sx1", "wsx_sx2")),
            db.or_(Rider.bio.is_(None), Rider.bio == ""),
        ).count()
        print(
            json.dumps(
                {
                    "twin_fill": twin_stats,
                    "ok_count": ok,
                    "fail_count": fail,
                    "still_without_bio": still,
                    "results": results,
                },
                indent=2,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
