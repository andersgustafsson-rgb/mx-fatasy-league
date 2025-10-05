# set_competition_coast.py
from app import app, db, Competition

MAP = {
    "Anaheim 1": "west",
    "San Diego": "west",
    "Anaheim 2 (Triple Crown)": "west",
    "Houston": "east",
    "Glendale": "west",
    "Seattle": "west",
    "Arlington": "east",
    "Daytona": "east",
    "Indianapolis": "east",
    "Birmingham": "both",   # Showdown
    "St. Louis": "both",    # Showdown
    "Detroit": "east",
    "Nashville": "east",
    "Cleveland": "east",
    "Philadelphia": "east",
    "Salt Lake City": "both",  # Showdown
    "Denver": "west",
}

def main():
    with app.app_context():
        rows = Competition.query.filter(Competition.series == "SX").all()
        touched = 0
        for c in rows:
            coast = MAP.get(c.name)
            print(f"CHECK: '{c.name}' -> coast in MAP: {coast} (current: {getattr(c, 'coast_250', None)})")
            if coast and getattr(c, "coast_250", None) != coast:
                c.coast_250 = coast
                touched += 1
                print(f"Set {c.name} -> {coast}")
        if touched:
            db.session.commit()
            print(f"KLART: uppdaterade {touched} tävlingar.")
        else:
            print("Inget att uppdatera. Kontrollera att kolumnen finns och att namn matchar exakt.")
            

if __name__ == "__main__":
    main()