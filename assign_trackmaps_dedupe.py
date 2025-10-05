# assign_trackmaps_name_map.py
# Kör: python assign_trackmaps_name_map.py
# Detta skript:
# - Läser bilder från static/trackmaps/2026
# - Hittar ronder via "RdXX_" i filnamn
# - Mappar ronder till rätt Competition via NAME_TO_ROUND (namn -> rond)
# - Deduplicerar varianter (-1024x768, -1, -2 osv) så bara en per motiv sparas
# - Rensar gamla CompetitionImage för respektive tävling innan den skriver nya

import os
import re
from pathlib import Path
from typing import Dict, List

from app import app, db, Competition, CompetitionImage

# 1) BYT DETTA VID BEHOV: Namn i DB -> rondnummer (1..17)
#    Se till att namnen matchar Competition.name exakt.
NAME_TO_ROUND: Dict[str, int] = {
    "Anaheim 1": 1,
    "San Diego": 2,
    "Anaheim 2 (Triple Crown)": 3,  # byt namn om du har annat namn i DB
    "Houston": 4,
    "Glendale": 5,
    "Seattle": 6,
    "Arlington": 7,
    "Daytona": 8,
    "Indianapolis": 9,
    "Birmingham": 10,
    "Detroit": 11,
    "St. Louis": 12,
    "Nashville": 13,
    "Cleveland": 14,
    "Philadelphia": 15,
    "Denver": 16,
    "Salt Lake City": 17,
}

# 2) Vart bilderna ligger
TRACK_DIR = Path("static/trackmaps/2026")

# 3) Rund‑mönster i filnamn: fångar "Rd01_", "Rd12_" etc
ROUND_RE = re.compile(r"Rd(\d{2})_", re.I)

# 4) Suffix som ofta ger visuella dubletter
VARIANT_SUFFIX_RE = re.compile(r"-(?:1024x768|[1-9])$", re.I)


def base_key(filename: str) -> str:
    """
    Basnyckel för "samma motiv – annan variant":
    - lowercase
    - ta bort -1024x768 och -1..-9 från namnets slut (utan extension)
    """
    name = filename.lower()
    stem, ext = os.path.splitext(name)
    stem = VARIANT_SUFFIX_RE.sub("", stem)
    return f"{stem}{ext}"


def pick_best_per_base(files: List[str]) -> List[str]:
    """
    Välj en bästa fil per base_key. Heuristik: längst filnamn vinner
    (brukar vara högre upplösning eller mer “komplett” URL).
    """
    best: Dict[str, str] = {}
    for fname in sorted(files):
        key = base_key(fname)
        cur = best.get(key)
        if cur is None or len(fname) > len(cur):
            best[key] = fname
    return sorted(best.values())


def collect_files_by_round() -> Dict[int, List[str]]:
    """
    Läs alla filer i TRACK_DIR, gruppera per rond 1..17 via ROUND_RE.
    """
    if not TRACK_DIR.exists():
        print("Saknar mapp:", TRACK_DIR.resolve())
        return {}

    files = sorted([f for f in TRACK_DIR.iterdir() if f.is_file()])
    if not files:
        print("Inga filer i:", TRACK_DIR.resolve())
        return {}

    by_round: Dict[int, List[str]] = {}
    seen = set()
    for f in files:
        if f.name in seen:
            continue
        seen.add(f.name)

        m = ROUND_RE.search(f.name)
        if not m:
            continue
        rnd = int(m.group(1))  # 1..17
        by_round.setdefault(rnd, []).append(f.name)

    return by_round


def main():
    by_round = collect_files_by_round()
    if not by_round:
        print("Hittade inga RdXX_-filer. Kontrollera filnamnen.")
        return

    with app.app_context():
        # Hämta alla SX‑tävlingar i DB, indexera på namn
        comps = Competition.query.filter(Competition.series == "SX").all()
        name_to_comp = {c.name: c for c in comps}

        # Verifiera att alla namn i NAME_TO_ROUND finns i DB
        missing = [name for name in NAME_TO_ROUND.keys() if name not in name_to_comp]
        if missing:
            print("FEL: Följande tävlingsnamn finns inte i databasen:")
            for n in missing:
                print(" -", n)
            print("Åtgärd: ändra NAME_TO_ROUND så att namnen matchar Competition.name i DB.")
            return

        total_created = 0
        for name, rnd in sorted(NAME_TO_ROUND.items(), key=lambda x: x[1]):
            comp = name_to_comp[name]
            files = by_round.get(rnd, [])

            # Informativ logg
            print(f"\n== Round {rnd:02d} -> {comp.event_date} {comp.name}")
            if not files:
                print("  [INFO] Inga filer hittades för denna rond. Rensar ev. gamla bilder i DB.")
                CompetitionImage.query.filter_by(competition_id=comp.id).delete()
                db.session.commit()
                continue

            # Deduplicera varianter i minnet
            files_unique = sorted(set(files))
            picked = pick_best_per_base(files_unique)

            # Rensa gamla bilder för denna tävling
            CompetitionImage.query.filter_by(competition_id=comp.id).delete()

            # Lägg in nya
            for idx, fname in enumerate(picked):
                url = f"trackmaps/2026/{fname}"
                db.session.add(
                    CompetitionImage(
                        competition_id=comp.id, image_url=url, sort_order=idx
                    )
                )
                total_created += 1

            print(
                f"  [OK] {comp.name}: {len(picked)} bilder (från {len(files_unique)} filer)"
            )

        db.session.commit()
        print(f"\nKLART: skapade totalt {total_created} CompetitionImage‑rader.")


if __name__ == "__main__":
    main()