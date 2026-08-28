"""Official SMX Combined 2026 standings (supermotocross.com) — end-of-season sync."""
from __future__ import annotations

from typing import Any

# (name, sx_points, mx_points) — authoritative for SMX Combined display / seeding.
OFFICIAL_SMX_450_2026: list[tuple[str, int, int]] = [
    ("Hunter Lawrence", 346, 442),
    ("Cooper Webb", 315, 230),
    ("Jorge Prado", 189, 351),
    ("Jett Lawrence", 0, 441),
    ("Dylan Ferrandis", 176, 265),
    ("Garrett Marchbanks", 142, 265),
    ("Haiden Deegan", 0, 376),
    ("Eli Tomac", 275, 89),
    ("Ken Roczen", 349, 0),
    ("Justin Cooper", 273, 74),
    ("R.J. Hampshire", 38, 308),
    ("Chase Sexton", 237, 61),
    ("Christian Craig", 154, 88),
    ("Jordon Smith", 68, 170),
    ("Malcolm Stewart", 203, 31),
    ("Justin Barcia", 31, 201),
    ("Aaron Plessinger", 98, 129),
    ("Mikkel Haarup", 0, 220),
    ("Joey Savatgy", 194, 0),
    ("Justin Hill", 188, 0),
    ("Mitchell Harrison", 73, 105),
    ("Shane McElrath", 150, 0),
    ("Colt Nichols", 121, 13),
    ("Benny Bloss", 0, 122),
    ("Cornelius Tøndel", 0, 112),
    ("Valentin Guillod", 0, 101),
    ("Vince Friese", 80, 14),
    ("Jason Anderson", 83, 0),
    ("Grant Harlan", 46, 28),
    ("Lorenzo Locurcio", 0, 61),
]

OFFICIAL_SMX_250_2026: list[tuple[str, int, int]] = [
    ("Cole Davies", 231, 378),
    ("Levi Kitchen", 177, 364),
    ("Ryder DiFrancesco", 164, 291),
    ("Chance Hymas", 38, 317),
    ("Julien Beaumer", 0, 322),
    ("Seth Hammaker", 180, 134),
    ("Carson Mumford", 70, 244),
    ("Kayden Minear", 27, 269),
    ("Jo Shimoda", 100, 194),
    ("Nate Thrasher", 137, 154),
    ("Daxton Bennick", 160, 118),
    ("Michael Mosiman", 107, 167),
    ("Haiden Deegan", 233, 0),
    ("Lux Turner", 86, 128),
    ("Caden Dudney", 44, 166),
    ("Max Vohland", 149, 57),
    ("Dilan Schwartz", 44, 144),
    ("Nick Romano", 72, 116),
    ("Hunter Yoder", 120, 64),
    ("Drew Adams", 30, 151),
    ("Max Anstie", 168, 0),
    ("Casey Cochran", 2, 146),
    ("Coty Schock", 140, 6),
    ("Landen Gordon", 13, 122),
    ("Henry Miller", 104, 26),
    ("Parker Ross", 90, 38),
    ("Avery Long", 58, 66),
    ("Devin Simonson", 124, 0),
    ("Derek Kelley", 94, 28),
    ("Marshal Weltin", 53, 68),
]


def _norm_name(name: str) -> str:
    return (name or "").strip().lower()


def official_smx_lookup(class_key: str) -> dict[str, tuple[int, int]]:
    rows = OFFICIAL_SMX_450_2026 if class_key == "450" else OFFICIAL_SMX_250_2026
    return {_norm_name(name): (sx, mx) for name, sx, mx in rows}


def apply_official_smx_2026_to_qualification(
    rankings: dict[str, list[tuple[str, dict]]],
    *,
    season_year: int,
) -> dict[str, list[tuple[str, dict]]]:
    """Replace computed SMX Combined rows with official 2026 totals when available."""
    if season_year != 2026:
        return rankings

    out: dict[str, list[tuple[str, dict]]] = {}
    for class_key in ("450", "250"):
        computed = {data["rider"].name: (key, data) for key, data in (rankings.get(class_key) or [])}
        official = OFFICIAL_SMX_450_2026 if class_key == "450" else OFFICIAL_SMX_250_2026

        merged: list[tuple[str, dict]] = []
        seen: set[str] = set()
        for name, sx, mx in official:
            key, data = computed.get(name, (None, None))
            if data is None:
                # Match by normalized name
                for rname, (rkey, rdata) in computed.items():
                    if _norm_name(rname) == _norm_name(name):
                        key, data = rkey, rdata
                        break
            if data is None:
                continue
            row = dict(data)
            row["sx_points"] = sx
            row["mx_points"] = mx
            row["total_points"] = sx + mx
            merged.append((key or f"official:{_norm_name(name)}", row))
            seen.add(_norm_name(name))

        # Keep computed riders outside official top-30 (shouldn't affect seed bubble)
        for key, data in rankings.get(class_key) or []:
            rname = data["rider"].name
            if _norm_name(rname) in seen:
                continue
            merged.append((key, data))

        merged.sort(key=lambda x: (-x[1]["total_points"], x[0]))
        out[class_key] = merged
    return out


def apply_official_smx_2026_to_championship_totals(
    totals: dict[tuple, dict[int, float]],
    rider_meta: dict[int, dict[str, Any]],
    *,
    season_year: int,
) -> None:
    """Patch SX/MX bucket totals so SMX Combined matches supermotocross.com (2026)."""
    if season_year != 2026:
        return

    id_by_name: dict[str, int] = {}
    for rid, meta in rider_meta.items():
        id_by_name[_norm_name(meta.get("rider_name") or "")] = int(rid)

    for name, sx, mx in OFFICIAL_SMX_450_2026:
        rid = id_by_name.get(_norm_name(name))
        if not rid:
            continue
        totals.setdefault(("sx", "450"), {})[rid] = float(sx)
        totals.setdefault(("mx", "450"), {})[rid] = float(mx)

    for name, sx, mx in OFFICIAL_SMX_250_2026:
        rid = id_by_name.get(_norm_name(name))
        if not rid:
            continue
        coast = str((rider_meta.get(rid) or {}).get("coast_250") or "").strip().lower()
        if coast not in ("east", "west"):
            continue
        totals.setdefault(("sx", "250", coast), {})[rid] = float(sx)
        totals.setdefault(("mx", "250", coast), {})[rid] = float(mx)


def reconcile_championship_results_2026(db, CompetitionResult, Competition) -> dict[str, int]:
    """
    Remove duplicate result rows for the same rider on the same race day.
    Safe to run on every deploy (idempotent).
    """
    from datetime import date

    today_year = date.today().year
    row = (
        Competition.query.filter(
            Competition.event_date.isnot(None),
            Competition.series.in_(("SX", "MX", "SMX", "WSX")),
        )
        .order_by(Competition.event_date.desc())
        .first()
    )
    season_year = int(row.event_date.year) if row and row.event_date else today_year

    rows = (
        db.session.query(CompetitionResult, Competition)
        .join(Competition, Competition.id == CompetitionResult.competition_id)
        .filter(Competition.series.in_(["SX", "MX"]))
        .all()
    )
    season_rows = [
        (cr, comp)
        for cr, comp in rows
        if comp.event_date and int(comp.event_date.year) == season_year
    ]
    if not season_rows:
        return {"deleted": 0, "season_year": season_year}

    by_comp_rider: dict[tuple[int, int], tuple] = {}
    for cr, comp in season_rows:
        key = (int(comp.id), int(cr.rider_id))
        prev = by_comp_rider.get(key)
        if prev is None or int(cr.result_id) > int(prev[0].result_id):
            by_comp_rider[key] = (cr, comp)

    by_race_rider: dict[tuple, tuple] = {}
    for cr, comp in by_comp_rider.values():
        coast = (comp.coast_250 or "").strip().lower()
        race_day = comp.event_date.isoformat() if comp.event_date else f"comp_{comp.id}"
        race_key = (
            str(comp.series).strip().upper(),
            race_day,
            coast,
            int(cr.rider_id),
        )
        prev = by_race_rider.get(race_key)
        if prev is None or int(cr.result_id) > int(prev[0].result_id):
            by_race_rider[race_key] = (cr, comp)

    kept_ids = {int(cr.result_id) for cr, _ in by_race_rider.values()}
    deleted = 0
    for cr, comp in season_rows:
        if int(cr.result_id) not in kept_ids:
            db.session.delete(cr)
            deleted += 1
    if deleted:
        db.session.commit()
    return {"deleted": deleted, "season_year": season_year}
