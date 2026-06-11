"""Bulk: hämta RacerX-bio för alla förare (eller de som saknar bio)."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from models import Rider, db  # noqa: E402
from racerx_rider_bio import (  # noqa: E402
    _normalize_rider_lookup_name,
    apply_profile_to_rider,
    copy_bio_between_riders,
    fetch_racerx_rider_profile,
    find_rider_with_bio_by_name,
    pick_primary_rider_for_name,
    sync_rider_twins,
)
from tools.apply_racerx_bio import _make_app  # noqa: E402


def _names_needing_bio(
    all_riders: list[Rider],
    *,
    refresh_all: bool,
    class_name: str,
) -> list[str]:
    names: set[str] = set()
    for rider in all_riders:
        if class_name and rider.class_name != class_name:
            continue
        if refresh_all or not (rider.bio or "").strip():
            key = _normalize_rider_lookup_name(rider.name or "")
            if key:
                names.add(key)
    return sorted(names)


def main() -> None:
    parser = argparse.ArgumentParser(description="Importera RacerX-bio för flera förare")
    parser.add_argument("--all", action="store_true", help="Uppdatera även förare som redan har bio")
    parser.add_argument("--limit", type=int, default=0, help="Max antal unika namn (0 = alla)")
    parser.add_argument("--delay", type=float, default=1.2, help="Sekunder mellan RacerX-anrop")
    parser.add_argument("--translate-sv", action="store_true", help="Översätt till svenska direkt efter import")
    parser.add_argument("--dry-run", action="store_true", help="Lista vilka som skulle köras")
    parser.add_argument("--class", dest="class_name", metavar="CLASS", help="Filtrera klass, t.ex. 450cc")
    args = parser.parse_args()

    app = _make_app()
    with app.app_context():
        print("DB:", app.config["SQLALCHEMY_DATABASE_URI"])
        all_riders = Rider.query.order_by(Rider.class_name, Rider.rider_number, Rider.name).all()
        name_keys = _names_needing_bio(
            all_riders,
            refresh_all=args.all,
            class_name=(args.class_name or "").strip(),
        )
        if args.limit > 0:
            name_keys = name_keys[: args.limit]

        plan: list[tuple[str, Rider, str]] = []
        for key in name_keys:
            primary = pick_primary_rider_for_name(key, riders=all_riders)
            if not primary:
                continue
            if args.class_name and primary.class_name != args.class_name:
                continue
            existing = find_rider_with_bio_by_name(key, riders=all_riders)
            mode = "copy" if existing and not args.all else "fetch"
            if mode == "copy" and not (primary.bio or "").strip():
                plan.append((key, primary, "copy"))
            elif mode == "fetch":
                plan.append((key, primary, "fetch"))

        print(f"Plan: {len(plan)} unika namn" + (" (dry-run)" if args.dry_run else ""))
        if args.dry_run:
            for key, rider, mode in plan[:50]:
                print(f"  {mode:5} #{rider.rider_number or '-':>3} {rider.class_name:8} {rider.name}")
            if len(plan) > 50:
                print(f"  ... +{len(plan) - 50} till")
            return

        ok = 0
        fail = 0
        for i, (key, rider, mode) in enumerate(plan, 1):
            name = (rider.name or "").strip()
            print(f"[{i}/{len(plan)}] {name} ({rider.class_name}, {mode})...", end=" ", flush=True)
            try:
                if mode == "copy":
                    source = find_rider_with_bio_by_name(key, riders=all_riders)
                    if not source or not copy_bio_between_riders(source, rider):
                        print("SKIP")
                        continue
                    twins = sync_rider_twins(rider, riders=all_riders)
                    synced = twins["bio"] + twins["portrait"]
                else:
                    profile = fetch_racerx_rider_profile(name)
                    if not profile.get("ok"):
                        print("MISS", profile.get("error", "?"))
                        fail += 1
                        time.sleep(args.delay)
                        continue
                    synced = apply_profile_to_rider(rider, profile, sync_twins=True)
                    if args.translate_sv and (rider.bio or "").strip():
                        from rider_bio_translate import ensure_swedish_bio

                        ensure_swedish_bio(rider)
                        sync_rider_twins(rider, riders=all_riders)
                db.session.commit()
                extra = f" +{len(synced)} dublett" if synced else ""
                print(f"OK{extra}")
                ok += 1
            except Exception as exc:
                db.session.rollback()
                print("ERR", exc)
                fail += 1
            if i < len(plan) and mode == "fetch":
                time.sleep(args.delay)

        print(json.dumps({"ok_count": ok, "fail_count": fail, "total": len(plan)}, indent=2))


if __name__ == "__main__":
    main()
