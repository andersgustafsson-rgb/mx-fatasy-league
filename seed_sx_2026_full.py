from datetime import date
from app import app, db, Competition

# Full AMA Supercross 2026 (Round 1–17) – datum enligt din lista
# is_triple_crown=True för Houston (R4), Indianapolis (R9), Cleveland (R14)
SX_2026 = [
    ("Anaheim 1",                    date(2026, 1, 10), False),
    ("San Diego",                    date(2026, 1, 17), False),
    ("Anaheim 2 (Triple Crown)",     date(2026, 1, 24), False),  # Eventet är inte TC i listan; namnet i DB kan behållas
    ("Houston",                      date(2026, 1, 31), True),
    ("Glendale",                     date(2026, 2, 7),  False),
    ("Seattle",                      date(2026, 2, 14), False),
    ("Arlington",                    date(2026, 2, 21), False),
    ("Daytona",                      date(2026, 2, 28), False),
    ("Indianapolis",                 date(2026, 3, 7),  True),
    ("Birmingham",                   date(2026, 3, 21), False),
    ("Detroit",                      date(2026, 3, 28), False),
    ("St. Louis",                    date(2026, 4, 4),  False),
    ("Nashville",                    date(2026, 4, 11), False),
    ("Cleveland",                    date(2026, 4, 18), True),
    ("Philadelphia",                 date(2026, 4, 25), False),
    ("Denver",                       date(2026, 5, 2),  False),
    ("Salt Lake City",               date(2026, 5, 9),  False),
]

def main():
    with app.app_context():
        # Hämta befintliga SX-tävlingar (så vi inte dubblar)
        existing = {c.name: c for c in Competition.query.filter_by(series="SX").all()}

        created = 0
        updated = 0
        for name, dt, tc in SX_2026:
            if name in existing:
                comp = existing[name]
                old = comp.event_date
                comp.event_date = dt
                try:
                    comp.is_triple_crown = 1 if tc else 0
                except Exception:
                    pass  # om fältet saknas, ignorera
                db.session.add(comp)
                updated += 1
                print(f"[UPD] {name}: {old} -> {dt} (TC={tc})")
            else:
                comp = Competition(
                    name=name,
                    event_date=dt,
                    series="SX",
                    point_multiplier=1.0,
                    is_triple_crown=1 if tc else 0
                )
                db.session.add(comp)
                created += 1
                print(f"[NEW] {name}: {dt} (TC={tc})")

        db.session.commit()
        print(f"KLART: skapade {created}, uppdaterade {updated} SX‑tävlingar.")

if __name__ == "__main__":
    main()