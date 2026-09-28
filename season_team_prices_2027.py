"""Proposed season-team rider prices for post-SMX 2026 reset → SMX 2027.

Budget: 1_500_000 for 2×450 + 2×250.
Design: top riders 500–600k so you cannot roster all elites.
Basis: AMA Combined SX+MX 2026 + SMX playoff form (through Playoff 2)
       + MXGP/MX2 2026 for Coenen brothers (AMA 2027 arrivals).

Load later via admin/script matching Rider.name (case-insensitive).
Do NOT apply until you confirm this list.
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

DEFAULT_PRICE = 100_000  # everyone else when loading
BUDGET = 1_500_000

# AMA season-team classes only (do not touch WSX / MXGP / MXoN rosters)
_AMA_SEASON_TEAM_CLASSES = frozenset({"450cc", "250cc"})


def _norm_name(name: str) -> str:
    return " ".join((name or "").casefold().split())


def apply_season_team_prices_2027(
    *,
    set_default_for_unlisted: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Write SEASON_TEAM_PRICES_2027 onto Rider.price for AMA 450/250.
    Matches Rider.name case-insensitively (aliases in the price map included).
    Unlisted AMA riders → DEFAULT_PRICE when set_default_for_unlisted=True.
    """
    from models import Rider, db

    price_by_norm = {_norm_name(n): p for n, p in SEASON_TEAM_PRICES_2027.items()}
    matched_keys: set[str] = set()
    updated: list[dict] = []
    unchanged: list[dict] = []
    defaulted: list[dict] = []

    riders = Rider.query.filter(Rider.class_name.in_(tuple(_AMA_SEASON_TEAM_CLASSES))).all()
    for rider in riders:
        key = _norm_name(rider.name)
        if key in price_by_norm:
            new_price = int(price_by_norm[key])
            matched_keys.add(key)
            if int(rider.price or 0) == new_price:
                unchanged.append(
                    {"id": rider.id, "name": rider.name, "class": rider.class_name, "price": new_price}
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
                }
            )
        elif set_default_for_unlisted:
            if int(rider.price or 0) == DEFAULT_PRICE:
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
                }
            )

    # Price-map names with no Rider row (typos / not in DB yet)
    missing = sorted(
        {n for n, p in SEASON_TEAM_PRICES_2027.items() if _norm_name(n) not in matched_keys}
    )

    if not dry_run and (updated or defaulted):
        db.session.commit()

    return {
        "ok": True,
        "dry_run": dry_run,
        "budget": BUDGET,
        "default_price": DEFAULT_PRICE,
        "updated_count": len(updated),
        "defaulted_count": len(defaulted),
        "unchanged_count": len(unchanged),
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
