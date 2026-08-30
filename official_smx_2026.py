"""Official SMX Combined 2026 standings (SX + MX) — after Ironman (round 28/28).

Source of truth for *totals* (synced 2026-08-30):
  https://www.supermotocross.com/results/standings/smx/450/
  https://www.supermotocross.com/results/standings/smx/250/

Why an overlay exists (2026 only):
  Live SX+MX sums from our imported results can drift (docked points, moto
  scoring edge cases, duplicate rows). Overlay keeps seeding/LCQ display in
  lockstep with supermotocross.com. **Next season: fix import/scoring so live
  sum is enough — do not keep a manual snapshot as the default.**

Playoff field: topp 20 = seeded (Direktkval), plats 21–30 = LCQ / last chance.
"""
from __future__ import annotations

from datetime import date
from typing import Any

# (name, sx_points, mx_points) — total = sx+mx must match supermotocross.com
# Order = official rank (important for ties, e.g. Shimoda before Mosiman).
OFFICIAL_SMX_450_2026: list[tuple[str, int, int]] = [
    ("Hunter Lawrence", 346, 474),   # 820
    ("Jorge Prado", 189, 401),       # 590
    ("Cooper Webb", 315, 264),       # 579
    ("Jett Lawrence", 0, 472),       # 472
    ("Dylan Ferrandis", 176, 269),   # 445
    ("Garrett Marchbanks", 142, 296),  # 438
    ("Haiden Deegan", 0, 404),       # 404
    ("Eli Tomac", 275, 121),         # 396
    ("R.J. Hampshire", 38, 346),     # 384
    ("Ken Roczen", 349, 0),          # 349
    ("Justin Cooper", 273, 74),      # 347
    ("Chase Sexton", 237, 61),       # 298
    ("Justin Barcia", 33, 226),      # 259
    ("Jordon Smith", 68, 191),       # 259
    ("Aaron Plessinger", 99, 159),   # 258
    ("Mikkel Haarup", 0, 246),       # 246
    ("Malcolm Stewart", 204, 41),    # 245
    ("Christian Craig", 154, 88),    # 242
    ("Joey Savatgy", 194, 0),        # 194
    ("Justin Hill", 188, 5),         # 193  ← seed cut (top 20)
    ("Mitchell Harrison", 73, 117),  # 190  ← LCQ 21
    ("Shane McElrath", 150, 0),      # 150
    ("Benny Bloss", 0, 139),         # 139
    ("Colt Nichols", 116, 19),       # 135
    ("Cornelius Tøndel", 0, 112),    # 112
    ("Valentin Guillod", 0, 101),    # 101
    ("Jason Anderson", 84, 0),       # 84
    ("Vince Friese", 66, 14),        # 80
    ("Grant Harlan", 48, 28),        # 76
    ("Fredrik Noren", 20, 50),       # 70 (site: Freddie Noren)
]

OFFICIAL_SMX_250_2026: list[tuple[str, int, int]] = [
    ("Cole Davies", 231, 407),       # 638
    ("Levi Kitchen", 177, 364),      # 541
    ("Ryder DiFrancesco", 164, 326),  # 490
    ("Chance Hymas", 38, 364),       # 402
    ("Julien Beaumer", 0, 369),      # 369
    ("Kayden Minear", 27, 297),      # 324
    ("Nate Thrasher", 137, 179),     # 316
    ("Seth Hammaker", 180, 134),     # 314
    ("Carson Mumford", 70, 244),     # 314
    ("Daxton Bennick", 160, 142),    # 302
    ("Jo Shimoda", 100, 194),        # 294
    ("Michael Mosiman", 107, 187),   # 294
    ("Haiden Deegan", 233, 0),       # 233 (SX 250 only — races 450 SMX)
    ("Lux Turner", 86, 141),         # 227
    ("Caden Dudney", 44, 174),       # 218
    ("Dilan Schwartz", 44, 164),     # 208
    ("Drew Adams", 25, 181),         # 206
    ("Max Vohland", 146, 57),        # 203
    ("Hunter Yoder", 121, 72),       # 193
    ("Landen Gordon", 36, 155),      # 191  ← seed cut (top 20)
    ("Nick Romano", 72, 116),        # 188  ← LCQ 21 (site: Nicholas Romano)
    ("Max Anstie", 168, 0),          # 168
    ("Casey Cochran", 2, 146),       # 148
    ("Coty Schock", 140, 6),         # 146
    ("Avery Long", 58, 84),          # 142
    ("Pierce Brown", 63, 68),        # 131
    ("Henry Miller", 104, 26),       # 130
    ("Parker Ross", 90, 39),         # 129
    ("Marshal Weltin", 53, 73),      # 126
    ("Devin Simonson", 124, 0),      # 124
]

# Alternate spellings on SMX.com / Racer X vs our Rider.name
_OFFICIAL_NAME_ALIASES: dict[str, str] = {
    "freddie noren": "fredrik noren",
    "nicholas romano": "nick romano",
    "rj hampshire": "r.j. hampshire",
    "r j hampshire": "r.j. hampshire",
    "tony cairoli": "antonio cairoli",
}


def _norm_name(name: str) -> str:
    n = (name or "").strip().lower()
    return _OFFICIAL_NAME_ALIASES.get(n, n)


def official_smx_lookup(class_key: str) -> dict[str, tuple[int, int]]:
    rows = OFFICIAL_SMX_450_2026 if class_key == "450" else OFFICIAL_SMX_250_2026
    return {_norm_name(name): (sx, mx) for name, sx, mx in rows}


def apply_official_smx_2026_to_qualification(
    rankings: dict[str, list[tuple[str, dict]]],
    *,
    season_year: int,
) -> dict[str, list[tuple[str, dict]]]:
    """Replace computed SMX Combined rows with official 2026 totals when available.

    Preserves official rank order (important for ties / seed vs LCQ cut).
    """
    if season_year != 2026:
        return rankings

    out: dict[str, list[tuple[str, dict]]] = {}
    for class_key in ("450", "250"):
        computed_by_norm: dict[str, tuple[str, dict]] = {}
        for key, data in rankings.get(class_key) or []:
            computed_by_norm[_norm_name(data["rider"].name)] = (key, data)

        official = OFFICIAL_SMX_450_2026 if class_key == "450" else OFFICIAL_SMX_250_2026

        merged: list[tuple[str, dict]] = []
        seen: set[str] = set()
        for name, sx, mx in official:
            norm = _norm_name(name)
            key, data = computed_by_norm.get(norm, (None, None))
            if data is None:
                continue
            row = dict(data)
            row["sx_points"] = sx
            row["mx_points"] = mx
            row["total_points"] = sx + mx
            merged.append((key or f"official:{norm}", row))
            seen.add(norm)

        extras: list[tuple[str, dict]] = []
        for key, data in rankings.get(class_key) or []:
            rname = _norm_name(data["rider"].name)
            if rname in seen:
                continue
            extras.append((key, data))
        extras.sort(key=lambda x: (-x[1]["total_points"], x[0]))
        merged.extend(extras)

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
