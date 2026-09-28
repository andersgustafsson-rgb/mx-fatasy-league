"""Proposed season-team rider prices for post-SMX 2026 reset → SMX 2027.

Budget: 2_000_000 for 2×450 + 2×250.
Design: top riders 500–600k so you cannot roster all elites.
Basis: AMA Combined SX+MX 2026 + SMX playoff form
       + MXGP/MX2 2026 for Coenen brothers (AMA 2027 arrivals).

Apply via admin Säsongsslut → Ladda priser:
  EVERY rider with SX / MX / SMX CompetitionResult gets a price
  (named tiers or DEFAULT_PRICE). Also covers remaining AMA 450/250 roster.
"""
from __future__ import annotations

# name -> price (fantasy units). Aliases included for DB spelling variants.
SEASON_TEAM_PRICES_2027: dict[str, int] = {
    # —— 450cc ——
    # Elite 600
    "Hunter Lawrence": 600_000,
    "Jorge Prado": 600_000,
    "Cooper Webb": 600_000,
    "Jett Lawrence": 600_000,
    # Near-elite 550
    "Haiden Deegan": 550_000,
    "Eli Tomac": 550_000,
    "Ken Roczen": 550_000,
    # Euro import / star+ 500
    "Lucas Coenen": 500_000,  # MXGP #6 2026, red plate, → AMA 450 2027
    # Star 480
    "Chase Sexton": 480_000,
    "Dylan Ferrandis": 480_000,
    "Garrett Marchbanks": 480_000,
    "Justin Cooper": 480_000,
    # Strong 400
    "R.J. Hampshire": 400_000,
    "Aaron Plessinger": 400_000,
    "Malcolm Stewart": 400_000,
    "Jordon Smith": 400_000,
    # Solid 320
    "Justin Barcia": 320_000,
    "Mikkel Haarup": 320_000,
    "Joey Savatgy": 320_000,
    "Justin Hill": 320_000,
    # Mid 250
    "Christian Craig": 250_000,
    "Shane McElrath": 250_000,
    "Mitchell Harrison": 250_000,
    "Benny Bloss": 250_000,
    # Depth 180
    "Colt Nichols": 180_000,
    "Jason Anderson": 180_000,
    "Cornelius Tøndel": 180_000,
    "Valentin Guillod": 180_000,
    "Vince Friese": 180_000,
    "Grant Harlan": 180_000,
    "Fredrik Noren": 180_000,
    "Freddie Noren": 180_000,
    "Lorenzo Locurcio": 180_000,
    "Dean Wilson": 180_000,
    "Jed Beaton": 180_000,
    "Mark Fineis": 180_000,
    "Antonio Cairoli": 180_000,
    "Tony Cairoli": 180_000,
    # —— 250cc ——
    # Elite 600
    "Cole Davies": 600_000,
    # Near-elite 550
    "Levi Kitchen": 550_000,
    "Ryder DiFrancesco": 550_000,
    "Ryder Difrancesco": 550_000,
    # Euro import / star+ 500
    "Sacha Coenen": 500_000,  # MX2 bronze #3 2026 → AMA 250 2027
    # Star 480
    "Chance Hymas": 480_000,
    "Julien Beaumer": 480_000,
    # Strong 400
    "Kayden Minear": 400_000,
    "Nate Thrasher": 400_000,
    "Seth Hammaker": 400_000,
    "Daxton Bennick": 400_000,
    # Solid 320
    "Carson Mumford": 320_000,
    "Jo Shimoda": 320_000,
    "Michael Mosiman": 320_000,
    "Drew Adams": 320_000,
    # Mid 250
    "Lux Turner": 250_000,
    "Caden Dudney": 250_000,
    "Dilan Schwartz": 250_000,
    "Max Vohland": 250_000,
    "Landen Gordon": 250_000,
    "Cameron McAdoo": 250_000,
    "Cameron Mcadoo": 250_000,
    # Depth 180
    "Pierce Brown": 180_000,
    "Hunter Yoder": 180_000,
    "Nick Romano": 180_000,
    "Nicholas Romano": 180_000,
    "Max Anstie": 180_000,
    "Marshal Weltin": 180_000,
    "Avery Long": 180_000,
    "Casey Cochran": 180_000,
    "Coty Schock": 180_000,
    "Henry Miller": 180_000,
    "Parker Ross": 180_000,
    "Devin Simonson": 180_000,
}

DEFAULT_PRICE = 100_000  # everyone else who raced SX/MX/SMX (and other AMA roster)
BUDGET = 2_000_000
DEPTH_PRICE = 100_000  # Combined standings ~31–50 / field fillers

# Extra Combined SX+MX names (beyond playoff top-30) so the full published
# top-50 lists are covered explicitly — same as DEFAULT but listed on purpose.
_COMBINED_DEPTH_450 = [
    "Lorenzo Locurcio",
    "Dean Wilson",
    "Jed Beaton",
    "Mark Fineis",
    # Lucas Coenen already in main map at 500k
    # Antonio/Tony Cairoli already in main map
    "Mitchell Oldenburg",
    "Kevin Moranz",
    "Roan Van De Moosdijk",
    "Dante Oliveira",
    "Stephen Rubini",
    "Jeremy Hand",
    # Devin Simonson is 250 in main map
    "Justin Rodbell",
    "Kyle Webster",
    "Cole Thompson",
    "Hamden Hudson",
    "Jack Chambers",
    "Cade Clason",
    "Tristan Lane",
]
_COMBINED_DEPTH_250 = [
    "Derek Kelley",
    # Cameron McAdoo already in main map
    # Sacha Coenen already in main map at 500k
    "Joshua Varize",
    "Gavin Towers",
    "Deacon Denno",
    "Kyle Peters",
    "Luke Neese",
    "Luke Clout",
    "Cullin Park",
    "Brodie Connolly",
    "Robbie Wageman",
    "Crockett Myers",
    "Izaih Clark",
    "Carson Wood",
    "Landon Gibson",
    "Alex Larwood",
    "Enzo Temmerman",
]

for _n in _COMBINED_DEPTH_450 + _COMBINED_DEPTH_250:
    SEASON_TEAM_PRICES_2027.setdefault(_n, DEPTH_PRICE)

# AMA season-team classes (do not touch WSX / MXGP / MXoN rosters)
_AMA_SEASON_TEAM_CLASSES = frozenset({"450cc", "250cc"})
_AMA_RESULT_SERIES = frozenset({"SX", "MX", "SMX"})


def _norm_name(name: str) -> str:
    return " ".join((name or "").casefold().split())


def _riders_who_raced_ama_season():
    """All Rider rows that have CompetitionResult in SX, MX or SMX playoffs."""
    from models import Competition, CompetitionResult, Rider, db

    raced_ids = {
        rid
        for (rid,) in (
            db.session.query(CompetitionResult.rider_id)
            .join(Competition, Competition.id == CompetitionResult.competition_id)
            .filter(db.func.upper(Competition.series).in_(tuple(_AMA_RESULT_SERIES)))
            .distinct()
            .all()
        )
        if rid
    }
    if not raced_ids:
        return []
    return Rider.query.filter(Rider.id.in_(raced_ids)).all()


def apply_season_team_prices_2027(
    *,
    set_default_for_unlisted: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Set Rider.price for EVERYONE who raced SX / MX / SMX playoffs (plus any
    remaining AMA 450/250 roster rows used by season-team builder).

    Named list → tiered prices. Everyone else who raced → DEFAULT_PRICE.
    Does not change WSX / MXGP / MXoN-only riders.
    """
    from models import Rider, db

    price_by_norm = {_norm_name(n): p for n, p in SEASON_TEAM_PRICES_2027.items()}
    matched_keys: set[str] = set()
    updated: list[dict] = []
    unchanged: list[dict] = []
    defaulted: list[dict] = []

    raced = _riders_who_raced_ama_season()
    raced_ids = {r.id for r in raced}

    # Also include AMA class roster (builder pool) even if a row somehow lacks results
    roster = Rider.query.filter(Rider.class_name.in_(tuple(_AMA_SEASON_TEAM_CLASSES))).all()
    by_id: dict[int, object] = {r.id: r for r in raced}
    for r in roster:
        by_id.setdefault(r.id, r)

    riders = list(by_id.values())
    already_default = 0
    skipped_non_ama = 0

    for rider in riders:
        cls = (rider.class_name or "").strip()
        # Never retarget WSX/MXGP class rows even if they somehow appear in results
        if cls and cls not in _AMA_SEASON_TEAM_CLASSES:
            skipped_non_ama += 1
            continue

        key = _norm_name(rider.name)
        if key in price_by_norm:
            new_price = int(price_by_norm[key])
            matched_keys.add(key)
            if int(rider.price or 0) == new_price:
                unchanged.append(
                    {
                        "id": rider.id,
                        "name": rider.name,
                        "class": rider.class_name,
                        "price": new_price,
                        "raced": rider.id in raced_ids,
                    }
                )
                continue
            old = int(rider.price or 0)
            if not dry_run:
                rider.price = new_price
            updated.append(
                {
                    "id": rider.id,
                    "name": rider.name,
                    "class": rider.class_name,
                    "old_price": old,
                    "new_price": new_price,
                    "raced": rider.id in raced_ids,
                }
            )
        elif set_default_for_unlisted:
            if int(rider.price or 0) == DEFAULT_PRICE:
                already_default += 1
                continue
            old = int(rider.price or 0)
            if not dry_run:
                rider.price = DEFAULT_PRICE
            defaulted.append(
                {
                    "id": rider.id,
                    "name": rider.name,
                    "class": rider.class_name,
                    "old_price": old,
                    "new_price": DEFAULT_PRICE,
                    "raced": rider.id in raced_ids,
                }
            )

    alias_of = {
        "freddie noren": "fredrik noren",
        "tony cairoli": "antonio cairoli",
        "nicholas romano": "nick romano",
    }
    missing = []
    for n in SEASON_TEAM_PRICES_2027:
        nk = _norm_name(n)
        if nk in matched_keys:
            continue
        canon = alias_of.get(nk, nk)
        if canon in matched_keys:
            continue
        missing.append(n)
    missing = sorted(set(missing))

    if not dry_run and (updated or defaulted):
        db.session.commit()

    named_matched = len(updated) + len(unchanged)
    priced_total = named_matched + len(defaulted) + already_default

    return {
        "ok": True,
        "dry_run": dry_run,
        "budget": BUDGET,
        "default_price": DEFAULT_PRICE,
        "raced_sx_mx_smx": len(raced),
        "total_ama_riders": len(riders) - skipped_non_ama,
        "named_matched": named_matched,
        "updated_count": len(updated),
        "unchanged_count": len(unchanged),
        "defaulted_count": len(defaulted),
        "already_default_count": already_default,
        "priced_total": priced_total,
        "skipped_non_ama": skipped_non_ama,
        "missing_names": missing,
        "updated": updated[:40],
        "defaulted": defaulted[:40],
    }


def unique_priced_rows() -> list[tuple[str, int, str]]:
    """Deduped display rows: (name, price, class_hint)."""
    cls_450 = {
        "Hunter Lawrence", "Jorge Prado", "Cooper Webb", "Jett Lawrence",
        "Haiden Deegan", "Eli Tomac", "Ken Roczen", "Lucas Coenen",
        "Chase Sexton", "Dylan Ferrandis", "Garrett Marchbanks", "Justin Cooper",
        "R.J. Hampshire", "Aaron Plessinger", "Malcolm Stewart", "Jordon Smith",
        "Justin Barcia", "Mikkel Haarup", "Joey Savatgy", "Justin Hill",
        "Christian Craig", "Shane McElrath", "Mitchell Harrison", "Benny Bloss",
        "Colt Nichols", "Jason Anderson", "Cornelius Tøndel", "Valentin Guillod",
        "Vince Friese", "Grant Harlan", "Fredrik Noren", "Lorenzo Locurcio",
        "Dean Wilson", "Jed Beaton", "Mark Fineis", "Antonio Cairoli",
    }
    skip_alias = {
        "Freddie Noren", "Tony Cairoli", "Ryder Difrancesco",
        "Nicholas Romano", "Cameron Mcadoo",
    }
    rows: list[tuple[str, int, str]] = []
    for name, price in SEASON_TEAM_PRICES_2027.items():
        if name in skip_alias:
            continue
        klass = "450cc" if name in cls_450 else "250cc"
        rows.append((name, price, klass))
    rows.sort(key=lambda r: (0 if r[2] == "450cc" else 1, -r[1], r[0]))
    return rows


if __name__ == "__main__":
    print(f"Budget {BUDGET:,} · default övriga {DEFAULT_PRICE:,}\n")
    cur = None
    for name, price, klass in unique_priced_rows():
        if klass != cur:
            cur = klass
            print(f"\n=== {klass} ===")
        print(f"{price:>7,}  {name}")
    print(f"\nTotalt namngivna: {len(unique_priced_rows())}")
