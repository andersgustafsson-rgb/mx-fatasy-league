"""AMA 2027 national / career numbers (official AMA release via Racer X, 29 Sep 2026).

Source:
  https://racerxonline.com/2026/09/29/ama-releases-2027-ama-supercross-motocross-and-supermotocross-national-numbers

Rules we follow in fantasy:
  - Store the assigned *professional* number (career or national), never the
    seasonal #1 title plates (those are per series/class champions).
  - Apply to AMA tippa classes only: 450cc + 250cc (not WSX / MXGP / MX2 rows).
  - Same rider id keeps picks/results; only ``rider_number`` changes.

#1 title plates (display-only elsewhere, not written to Rider.rider_number):
  450 SMX Jorge Prado · 450 SX Ken Roczen · 450 MX Hunter Lawrence
  250 SMX Levi Kitchen · 250 MX Cole Davies · 250 SX East Cole Davies
  250 SX West Haiden Deegan
"""
from __future__ import annotations

from typing import Any

# Official AMA professional numbers for 2027 (career + national).
# Keys are AMA display names as published. Values are integers 2–99.
AMA_2027_NATIONAL_NUMBERS: dict[str, int] = {
    "Cooper Webb": 2,
    "Eli Tomac": 3,
    "Chase Sexton": 4,
    "Cole Davies": 5,  # new career
    "Aaron Plessinger": 7,
    "Ryder DiFrancesco": 10,  # new career
    "Kyle Chisholm": 11,
    "Shane McElrath": 12,
    "Dylan Ferrandis": 14,
    "Dean Wilson": 15,
    "Chance Hymas": 16,
    "Joey Savatgy": 17,
    "Jett Lawrence": 18,
    "Julien Beaumer": 19,
    "Kayden Minear": 20,
    "Jason Anderson": 21,
    "Nate Thrasher": 22,
    "Seth Hammaker": 23,
    "RJ Hampshire": 24,
    "Carson Mumford": 25,
    "Daxton Bennick": 26,
    "Malcolm Stewart": 27,
    "Christian Craig": 28,
    "Michael Mosiman": 29,
    "Jo Shimoda": 30,
    "Jordon Smith": 31,
    "Justin Cooper": 32,
    "Mikkel Haarup": 33,
    "Lux Turner": 34,
    "Caden Dudney": 35,
    "Garrett Marchbanks": 36,
    "Dilan Schwartz": 37,
    "Haiden Deegan": 38,
    "Drew Adams": 39,
    "Max Vohland": 40,
    "Hunter Yoder": 41,
    "Landen Gordon": 42,
    "Mitchell Harrison": 43,
    "Nick Romano": 44,
    "Colt Nichols": 45,
    "Justin Hill": 46,
    "Levi Kitchen": 47,
    "Max Anstie": 48,
    "Casey Cochran": 49,
    "Coty Schock": 50,
    "Justin Barcia": 51,
    "Devin Simonson": 52,
    "Avery Long": 53,
    "Benny Bloss": 54,
    "Pierce Brown": 55,
    "Henry Miller": 56,
    "Parker Ross": 57,
    "Marshal Weltin": 58,
    "Derek Kelley": 59,
    "Cornelius Tondel": 60,
    "Jorge Prado": 61,  # new career
    "Valentin Guillod": 62,
    "Cameron McAdoo": 63,
    "Sacha Coenen": 64,
    "Vince Friese": 65,
    "Joshua Varize": 66,
    "Grant Harlan": 67,
    "Gavin Towers": 68,
    "Fredrik Noren": 69,
    "Deacon Denno": 70,
    "Lorenzo Locurcio": 71,
    "Jed Beaton": 72,
    "Mark Fineis": 73,
    "Justin Rodbell": 74,
    "Jeremy Hand": 75,
    "Kyle Peters": 76,
    "Luke Neese": 77,
    "Luke Clout": 78,
    "Lucas Coenen": 79,
    "Antonio Cairoli": 80,
    "Cullin Park": 81,
    "Brodie Connolly": 82,
    "Robbie Wageman": 83,
    "Crockett Myers": 84,
    "Mitchell Oldenburg": 85,
    "Izaih Clark": 86,
    "Carson Wood": 87,
    "Landon Gibson": 88,
    "Alex Larwood": 89,
    "Enzo Temmerman": 90,
    "Kevin Moranz": 91,
    "Cole Thompson": 92,
    "Anthony Bourdon": 93,
    "Ken Roczen": 94,
    "Matti Jorgensen": 95,
    "Hunter Lawrence": 96,
    "Francisco Garcia": 97,
    "Jalek Swoll": 98,
    "Roan Van De Moosdijk": 99,
}

# DB / tippa name variants → canonical AMA list name
AMA_2027_NAME_ALIASES: dict[str, str] = {
    "Ryder Difrancesco": "Ryder DiFrancesco",
    "R.J. Hampshire": "RJ Hampshire",
    "RJ Hampshire": "RJ Hampshire",
    "Maximus Vohland": "Max Vohland",
    "Cameron Mcadoo": "Cameron McAdoo",
    "Cornelius Tøndel": "Cornelius Tondel",
    "Cornelius Tondel": "Cornelius Tondel",
    "Roan van de Moosdijk": "Roan Van De Moosdijk",
    "Roan Van de Moosdijk": "Roan Van De Moosdijk",
}

AMA_TIPPA_CLASSES = frozenset({"450cc", "250cc"})

# Riders on the official list but historically missing from AMA tippa roster.
# Created only when no 450cc/250cc row exists (WSX/MXGP rows are left alone).
AMA_2027_ENSURE_RIDERS: list[dict[str, Any]] = [
    {
        "name": "Kyle Chisholm",
        "class_name": "450cc",
        "rider_number": 11,
        "bike_brand": "Unknown",
        "price": 100_000,
    },
    {
        "name": "Luke Clout",
        "class_name": "450cc",
        "rider_number": 78,
        "bike_brand": "Unknown",
        "price": 100_000,
    },
    {
        "name": "Alex Larwood",
        "class_name": "250cc",
        "rider_number": 89,
        "bike_brand": "Unknown",
        "price": 100_000,
    },
]

SOURCE_URL = (
    "https://racerxonline.com/2026/09/29/"
    "ama-releases-2027-ama-supercross-motocross-and-supermotocross-national-numbers"
)
SOURCE_DATE = "2026-09-29"


def normalize_ama_name(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return ""
    if raw in AMA_2027_NAME_ALIASES:
        return AMA_2027_NAME_ALIASES[raw]
    # case-insensitive alias hit
    lower_map = {k.lower(): v for k, v in AMA_2027_NAME_ALIASES.items()}
    if raw.lower() in lower_map:
        return lower_map[raw.lower()]
    # case-insensitive official list hit
    for official in AMA_2027_NATIONAL_NUMBERS:
        if official.lower() == raw.lower():
            return official
    return raw


def expected_number_for_name(name: str) -> int | None:
    canon = normalize_ama_name(name)
    return AMA_2027_NATIONAL_NUMBERS.get(canon)


def plan_ama_2027_number_updates(
    riders: list[Any],
    *,
    classes: frozenset[str] = AMA_TIPPA_CLASSES,
) -> dict[str, Any]:
    """Compare AMA tippa riders to the official 2027 list.

    Returns a structured plan: updates, already_ok, missing_in_db, unmatched_in_db.
    """
    by_canon: dict[str, list[Any]] = {}
    unmatched: list[dict[str, Any]] = []
    for r in riders:
        if (getattr(r, "class_name", None) or "") not in classes:
            continue
        canon = normalize_ama_name(getattr(r, "name", "") or "")
        if canon in AMA_2027_NATIONAL_NUMBERS:
            by_canon.setdefault(canon, []).append(r)
        else:
            unmatched.append(
                {
                    "id": getattr(r, "id", None),
                    "name": getattr(r, "name", None),
                    "class_name": getattr(r, "class_name", None),
                    "rider_number": getattr(r, "rider_number", None),
                }
            )

    updates: list[dict[str, Any]] = []
    already_ok: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []

    for canon, num in AMA_2027_NATIONAL_NUMBERS.items():
        matches = by_canon.get(canon) or []
        if not matches:
            continue
        if len(matches) > 1:
            # Prefer keeping one row per class; still flag ambiguity
            ambiguous.append(
                {
                    "name": canon,
                    "target": num,
                    "matches": [
                        {
                            "id": r.id,
                            "class_name": r.class_name,
                            "rider_number": r.rider_number,
                        }
                        for r in matches
                    ],
                }
            )
        for r in matches:
            cur = getattr(r, "rider_number", None)
            row = {
                "id": r.id,
                "name": getattr(r, "name", None),
                "canon_name": canon,
                "class_name": r.class_name,
                "old": cur,
                "new": num,
            }
            if cur == num:
                already_ok.append(row)
            else:
                updates.append(row)

    missing_in_db = sorted(
        n for n in AMA_2027_NATIONAL_NUMBERS if n not in by_canon
    )

    updates.sort(key=lambda x: (x["class_name"] or "", int(x["new"]), x["name"] or ""))
    already_ok.sort(key=lambda x: (x["class_name"] or "", int(x["new"]), x["name"] or ""))

    return {
        "source_url": SOURCE_URL,
        "source_date": SOURCE_DATE,
        "classes": sorted(classes),
        "list_size": len(AMA_2027_NATIONAL_NUMBERS),
        "updates": updates,
        "already_ok": already_ok,
        "missing_in_db": missing_in_db,
        "unmatched_in_db": unmatched,
        "ambiguous": ambiguous,
        "summary": {
            "to_change": len(updates),
            "already_ok": len(already_ok),
            "missing_in_db": len(missing_in_db),
            "unmatched_in_db": len(unmatched),
            "ambiguous": len(ambiguous),
        },
    }


def ensure_missing_ama_2027_riders(
    *,
    rider_model,
    db_session,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Create AMA tippa rows for official-list riders missing from 450/250."""
    created: list[dict[str, Any]] = []
    skipped: list[str] = []
    for spec in AMA_2027_ENSURE_RIDERS:
        name = spec["name"]
        existing = (
            rider_model.query.filter(
                rider_model.class_name.in_(list(AMA_TIPPA_CLASSES)),
            )
            .filter(rider_model.name.ilike(name))
            .first()
        )
        if existing:
            skipped.append(name)
            continue
        created.append(dict(spec))
        if dry_run:
            continue
        rider = rider_model(
            name=spec["name"],
            class_name=spec["class_name"],
            rider_number=int(spec["rider_number"]),
            bike_brand=spec.get("bike_brand") or "Unknown",
            price=int(spec.get("price") or 100_000),
            series_participation="all",
        )
        db_session.add(rider)
    if not dry_run and created:
        db_session.commit()
    return {
        "dry_run": dry_run,
        "would_create" if dry_run else "created": created,
        "already_present": skipped,
    }


def apply_ama_2027_number_plan(
    plan: dict[str, Any],
    *,
    rider_model,
    db_session,
    riders_query,
    dry_run: bool = True,
    ensure_missing: bool = True,
) -> dict[str, Any]:
    """Apply ``plan['updates']`` via entry_list_import.apply_number_updates."""
    from entry_list_import import apply_number_updates

    ensure_info: dict[str, Any] = {}
    if ensure_missing:
        ensure_info = ensure_missing_ama_2027_riders(
            rider_model=rider_model,
            db_session=db_session,
            dry_run=dry_run,
        )
        if not dry_run:
            # Refresh plan after creating missing riders so they get numbers too
            riders = riders_query.filter(
                rider_model.class_name.in_(list(AMA_TIPPA_CLASSES))
            ).all()
            plan = plan_ama_2027_number_updates(riders)

    number_updates = [
        {
            "existing_id": u["id"],
            "name": u["name"],
            "class_name": u["class_name"],
            "number": u["new"],
            "number_changed": True,
        }
        for u in plan.get("updates") or []
    ]
    if dry_run:
        return {
            "dry_run": True,
            "would_update": len(number_updates),
            "names": [u["name"] for u in plan.get("updates") or []],
            "plan_summary": plan.get("summary"),
            "missing_in_db": plan.get("missing_in_db"),
            "ensure": ensure_info,
            "changes_preview": [
                {
                    "name": u["name"],
                    "class_name": u["class_name"],
                    "old": u["old"],
                    "new": u["new"],
                }
                for u in (plan.get("updates") or [])[:40]
            ],
        }

    updated, errors, conflicts = apply_number_updates(
        number_updates,
        rider_model,
        db_session,
        riders_query,
        auto_commit=True,
    )
    return {
        "dry_run": False,
        "updated": updated,
        "errors": errors,
        "conflicts_resolved": conflicts,
        "ensure": ensure_info,
        "plan_summary": plan.get("summary"),
    }
