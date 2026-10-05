"""Clean false AMA 450/250 duplicates after 2027 number apply.

Policy (stats-first):
  - If a rider truly raced both classes in 2026, KEEP both rows.
  - Delete/reclass only clear mistakes (empty wrong class, or Webb fake-250).

Racer X current class used as guide; competition_results decide whether the
other class row is real history.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import text

from main import app
from models import Rider, db

# Tables that reference riders — remap then delete.
RIDER_FK_COLS = [
    ("competition_results", "rider_id"),
    ("competition_rider_status", "rider_id"),
    ("holeshot_picks", "rider_id"),
    ("holeshot_results", "rider_id"),
    ("qualifying_picks", "rider_id"),
    ("qualifying_results", "rider_id"),
    ("race_picks", "rider_id"),
    ("wildcard_picks", "rider_id"),
    ("season_team_riders", "rider_id"),
    ("season_team_class_promotions", "from_rider_id"),
    ("season_team_class_promotions", "to_rider_id"),
    ("mxon_team_entries", "rider_id"),
    ("league_challenges", "challenger_rider_id"),
    ("league_challenges", "challenger_guess_rider_id"),
    ("league_challenges", "challenged_rider_id"),
]


def _count_refs(rider_id: int) -> dict[str, int]:
    out: dict[str, int] = {}
    for table, col in RIDER_FK_COLS:
        try:
            n = db.session.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE {col} = :id"),
                {"id": rider_id},
            ).scalar()
        except Exception:
            continue
        if n:
            out[f"{table}.{col}"] = int(n)
    return out


def _remap_all(from_id: int, to_id: int) -> dict[str, int]:
    moved: dict[str, int] = {}
    for table, col in RIDER_FK_COLS:
        try:
            # Skip rows that would collide on unique (competition_id, rider_id) etc.
            # Prefer: update where no conflict; delete leftover from_id rows.
            n = db.session.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE {col} = :fid"),
                {"fid": from_id},
            ).scalar()
            if not n:
                continue
            # Generic update — if unique violation, delete source row instead.
            try:
                db.session.execute(
                    text(f"UPDATE {table} SET {col} = :tid WHERE {col} = :fid"),
                    {"tid": to_id, "fid": from_id},
                )
                moved[f"{table}.{col}"] = int(n)
            except Exception:
                db.session.rollback()
                # Fall back: drop source refs that can't move
                db.session.execute(
                    text(f"DELETE FROM {table} WHERE {col} = :fid"),
                    {"fid": from_id},
                )
                moved[f"{table}.{col}"] = int(n)
                print(f"  ! {table}.{col}: could not remap, deleted {n} from {from_id}")
        except Exception as e:
            print(f"  ERR {table}.{col}: {e}")
    return moved


def _delete_rider(rider_id: int) -> None:
    # Wipe remaining refs then delete
    for table, col in RIDER_FK_COLS:
        try:
            db.session.execute(
                text(f"DELETE FROM {table} WHERE {col} = :id"),
                {"id": rider_id},
            )
        except Exception:
            pass
    db.session.execute(text("DELETE FROM riders WHERE id = :id"), {"id": rider_id})


def main() -> int:
    dry = "--apply" not in sys.argv
    with app.app_context():
        actions: list[str] = []

        # --- Cooper Webb: fake 250 (527) is actually WSX results; merge into wsx_sx1 936 ---
        webb_ama = Rider.query.get(463)
        webb_fake250 = Rider.query.get(527)
        webb_wsx = Rider.query.get(936)
        if webb_fake250 and webb_fake250.class_name == "250cc":
            if webb_wsx and webb_wsx.class_name == "wsx_sx1":
                # Prefer keeping 527 (has WSX results) as wsx_sx1, merge 936 → 527, drop 936
                actions.append(
                    f"Webb: reclass id=527 250cc→wsx_sx1, remap id=936→527, delete 936 "
                    f"(450 id={webb_ama.id if webb_ama else None} kept)"
                )
                if not dry:
                    webb_fake250.class_name = "wsx_sx1"
                    webb_fake250.coast_250 = None
                    db.session.flush()
                    _remap_all(936, 527)
                    _delete_rider(936)
            else:
                actions.append("Webb: reclass id=527 250cc→wsx_sx1 (no wsx twin)")
                if not dry:
                    webb_fake250.class_name = "wsx_sx1"
                    webb_fake250.coast_250 = None

        # --- Empty / near-empty wrong-class rows ---
        # Locurcio 250 empty, Fineis 250 empty, Weltin 450 (1 wildcard only)
        simple_deletes = [
            (420, "Lorenzo Locurcio", "250cc", "empty wrong class; keep 450 id=626"),
            (418, "Mark Fineis", "250cc", "empty wrong class; keep 450 id=776"),
            (475, "Marshal Weltin", "450cc", "no results; keep 250 id=581 (RX 250)"),
        ]
        for rid, name, cls, why in simple_deletes:
            r = Rider.query.get(rid)
            if not r:
                actions.append(f"skip {name} id={rid}: already gone")
                continue
            if r.class_name != cls:
                actions.append(
                    f"skip {name} id={rid}: class is {r.class_name}, expected {cls}"
                )
                continue
            refs = _count_refs(rid)
            actions.append(f"DELETE {name} id={rid} ({cls}) — {why}; refs={refs or '{}'}")
            if not dry:
                _delete_rider(rid)

        # Dual-class with real 2026 results in BOTH — keep
        keep_both = [
            "Devin Simonson",
            "Valentin Guillod",
            "Justin Rodbell",
            "Jeremy Hand",
            "Matti Jorgensen",
        ]
        for name in keep_both:
            rows = (
                Rider.query.filter(Rider.name.ilike(name))
                .filter(Rider.class_name.in_(["450cc", "250cc"]))
                .all()
            )
            actions.append(
                f"KEEP BOTH {name}: "
                + ", ".join(f"id={r.id} {r.class_name}#{r.rider_number}" for r in rows)
                + " (real results in both classes 2026)"
            )

        if dry:
            print("DRY-RUN — pass --apply to write\n")
        else:
            db.session.commit()
            print("APPLIED\n")
        for a in actions:
            print("-", a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
