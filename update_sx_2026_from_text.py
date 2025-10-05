from datetime import datetime
from app import app, db, Competition

# SX 2026 – Round 1–17 (ort, datum, triple crown?)
# OBS: Vi sätter INTE venue här (så du slipper schemaändring).
RAW_EVENTS = [
    ("Anaheim, CA",         "Jan 10, 2026", False),  # Round 1
    ("San Diego, CA",       "Jan 17, 2026", False),  # Round 2
    ("Anaheim, CA",         "Jan 24, 2026", False),  # Round 3
    ("Houston, TX",         "Jan 31, 2026", True),   # Round 4 (Triple Crown)
    ("Glendale, AZ",        "Feb 07, 2026", False),  # Round 5
    ("Seattle, WA",         "Feb 14, 2026", False),  # Round 6
    ("Arlington, TX",       "Feb 21, 2026", False),  # Round 7
    ("Daytona Beach, FL",   "Feb 28, 2026", False),  # Round 8
    ("Indianapolis, IN",    "Mar 07, 2026", True),   # Round 9 (Triple Crown)
    ("Birmingham, AL",      "Mar 21, 2026", False),  # Round 10 (E/W Showdown)
    ("Detroit, MI",         "Mar 28, 2026", False),  # Round 11
    ("St. Louis, MO",       "Apr 04, 2026", False),  # Round 12 (E/W Showdown)
    ("Nashville, TN",       "Apr 11, 2026", False),  # Round 13
    ("Cleveland, OH",       "Apr 18, 2026", True),   # Round 14 (Triple Crown)
    ("Philadelphia, PA",    "Apr 25, 2026", False),  # Round 15
    ("Denver, CO",          "May 02, 2026", False),  # Round 16
    ("Salt Lake City, UT",  "May 09, 2026", False),  # Round 17
]

def parse_date(s: str):
    return datetime.strptime(s, "%b %d, %Y").date()

def main():
    with app.app_context():
        comps = Competition.query.filter(Competition.series == "SX").all()
        updated = 0

        # Ordna events per ort (Anaheim har två datum)
        events_by_city = {}
        for city, dstr, is_tc in RAW_EVENTS:
            events_by_city.setdefault(city, []).append((parse_date(dstr), is_tc))

        for comp in comps:
            name_l = comp.name.lower()

            # Specialfall: skilj Anaheim 1 och Anaheim 2
            if "anaheim" in name_l:
                if " 1" in name_l or name_l.endswith(" 1"):
                    # Anaheim 1 -> Jan 10, 2026
                    choice = next(
                        (e for e in events_by_city.get("Anaheim, CA", [])
                         if e[0] == parse_date("Jan 10, 2026")),
                        None
                    )
                    if choice:
                        dt, is_tc = choice
                        old_date = comp.event_date
                        comp.event_date = dt
                        try:
                            comp.is_triple_crown = 1 if is_tc else 0
                        except Exception:
                            pass  # om fältet saknas, ignorera
                        db.session.add(comp); updated += 1
                        print(f"[OK] (Anaheim 1) {comp.name}: {old_date} -> {comp.event_date}")
                    else:
                        print(f"[MISS DATUM] (Anaheim 1) {comp.name}")
                    continue

                elif " 2" in name_l or name_l.endswith(" 2"):
                    # Anaheim 2 -> Jan 24, 2026
                    choice = next(
                        (e for e in events_by_city.get("Anaheim, CA", [])
                         if e[0] == parse_date("Jan 24, 2026")),
                        None
                    )
                    if choice:
                        dt, is_tc = choice
                        old_date = comp.event_date
                        comp.event_date = dt
                        try:
                            comp.is_triple_crown = 1 if is_tc else 0
                        except Exception:
                            pass
                        db.session.add(comp); updated += 1
                        print(f"[OK] (Anaheim 2) {comp.name}: {old_date} -> {comp.event_date}")
                    else:
                        print(f"[MISS DATUM] (Anaheim 2) {comp.name}")
                    continue

            # Övriga – matcha orten som substring i Competition.name
            matched = False
            for city in events_by_city.keys():
                city_key = city.split(",")[0].lower()  # t.ex. "san diego"
                if city_key in name_l:
                    dt, is_tc = events_by_city[city][0]
                    old_date = comp.event_date
                    comp.event_date = dt
                    try:
                        comp.is_triple_crown = 1 if is_tc else 0
                    except Exception:
                        pass
                    db.session.add(comp); updated += 1
                    matched = True
                    print(f"[OK] {comp.name}: {old_date} -> {comp.event_date}")
                    break

            if not matched:
                print(f"[SKIP] Ingen ortmatchning för: {comp.name}")

        db.session.commit()
        print(f"KLART: uppdaterade {updated} SX‑tävlingar.")

if __name__ == "__main__":
    main()