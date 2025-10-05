import re
from pathlib import Path
from app import app, db, Competition, CompetitionImage

TRACK_DIR = Path("static/trackmaps/2026")
PATTERN = re.compile(r"Rd(\d{2})_", re.I)  # matchar "Rd01_", "Rd12_" etc.

def main():
    if not TRACK_DIR.exists():
        print("Saknar mapp:", TRACK_DIR.resolve())
        return

    files = sorted([f for f in TRACK_DIR.iterdir() if f.is_file()])
    if not files:
        print("Inga filer i:", TRACK_DIR.resolve())
        return

    # Grupp: round -> [filnamn]
    by_round = {}
    for f in files:
        m = PATTERN.search(f.name)
        if not m:
            continue
        rnd = int(m.group(1))  # 1..17
        by_round.setdefault(rnd, []).append(f.name)

    with app.app_context():
        comps = (Competition.query
                 .filter(Competition.series == "SX")
                 .order_by(Competition.event_date.asc())
                 .all())

        if len(comps) != 17:
            print(f"Varning: förväntade 17 SX-tävlingar, hittade {len(comps)}. Avbryter för säkerhet.")
            for c in comps:
                print(c.name, c.event_date)
            return

        # Round 1..17 mappas till tävlingar i datumordning
        round_to_comp = {i + 1: comp for i, comp in enumerate(comps)}

        created = 0
        for rnd, comp in round_to_comp.items():
            images = by_round.get(rnd, [])
            if not images:
                print(f"[INFO] Inga filer hittades för Round {rnd}: {comp.name}")
                continue

            # Rensa gamla bilder för denna tävling (om du kör om)
            CompetitionImage.query.filter_by(competition_id=comp.id).delete()

            for idx, fname in enumerate(sorted(images)):
                url = f"trackmaps/2026/{fname}"
                ci = CompetitionImage(competition_id=comp.id, image_url=url, sort_order=idx)
                db.session.add(ci)
                created += 1
            print(f"[OK] Round {rnd}: {comp.name} -> {len(images)} bilder")

        db.session.commit()
        print(f"KLART: skapade {created} CompetitionImage-rader.")

if __name__ == "__main__":
    main()