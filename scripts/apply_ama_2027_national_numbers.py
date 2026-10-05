"""Dry-run / apply AMA 2027 national numbers against local or configured DB.

Usage:
  python scripts/apply_ama_2027_national_numbers.py           # dry-run
  python scripts/apply_ama_2027_national_numbers.py --apply   # write DB
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="AMA 2027 national numbers")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write rider_number changes (default is dry-run)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full plan as JSON",
    )
    args = parser.parse_args()

    from main import app
    from models import Rider, db
    from ama_2027_national_numbers import (
        apply_ama_2027_number_plan,
        plan_ama_2027_number_updates,
    )

    with app.app_context():
        riders = Rider.query.filter(Rider.class_name.in_(["450cc", "250cc"])).all()
        plan = plan_ama_2027_number_updates(riders)
        s = plan["summary"]
        print(
            f"AMA 2027 numbers · list={plan['list_size']} · "
            f"change={s['to_change']} ok={s['already_ok']} "
            f"missing={s['missing_in_db']} unmatched={s['unmatched_in_db']} "
            f"ambiguous={s['ambiguous']}"
        )
        print(f"Source: {plan['source_url']} ({plan['source_date']})")
        print()
        if plan["updates"]:
            print("Changes:")
            for u in plan["updates"]:
                print(
                    f"  #{u['old']:>3} → #{u['new']:<3}  "
                    f"{u['class_name']:<6}  {u['name']}"
                )
            print()
        if plan["missing_in_db"]:
            print("In AMA list but not in DB (450/250):")
            for n in plan["missing_in_db"]:
                print(f"  + {n}  → #{AMA_NUM(n)}")
            print()
        if plan["ambiguous"]:
            print("Ambiguous (multiple DB rows for one AMA name):")
            for a in plan["ambiguous"]:
                print(f"  ! {a['name']} → #{a['target']}: {a['matches']}")
            print()
        if args.json:
            print(json.dumps(plan, ensure_ascii=False, indent=2, default=str))

        result = apply_ama_2027_number_plan(
            plan,
            rider_model=Rider,
            db_session=db.session,
            riders_query=Rider.query,
            dry_run=not args.apply,
            ensure_missing=True,
        )
        if args.apply:
            ensure = result.get("ensure") or {}
            created = ensure.get("created") or []
            print(
                f"Applied: {len(result.get('updated') or [])} updated, "
                f"{result.get('conflicts_resolved') or 0} conflicts, "
                f"{len(result.get('errors') or [])} errors, "
                f"{len(created)} created"
            )
            for c in created:
                print(f"  + {c.get('name')} #{c.get('rider_number')} ({c.get('class_name')})")
            for e in result.get("errors") or []:
                print(f"  ERR {e}")
        else:
            ensure = result.get("ensure") or {}
            would = ensure.get("would_create") or []
            print(
                f"Dry-run only — would update {result.get('would_update')} riders, "
                f"create {len(would)}. Pass --apply to write."
            )
            for c in would:
                print(f"  + would create {c.get('name')} #{c.get('rider_number')} ({c.get('class_name')})")
    return 0


def AMA_NUM(name: str) -> int:
    from ama_2027_national_numbers import AMA_2027_NATIONAL_NUMBERS

    return AMA_2027_NATIONAL_NUMBERS[name]


if __name__ == "__main__":
    raise SystemExit(main())
