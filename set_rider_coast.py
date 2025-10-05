# set_rider_coast.py
from app import app, db, Rider

# Fyll listorna med exakta namn som de står i din DB (riders.name)
# Jag har fyllt en vanlig/van ryttaruppdelning som brukar gälla – justera efter din 2026-lista vid behov.

WEST = [
    "Haiden Deegan",
    "Levi Kitchen",
    "Jo Shimoda",       # justera om han kör East 2026
    "Jalek Swoll",
    "Ryder DiFrancesco",
    "Dilan Schwartz",
    "Guillem Farres",
    "Hardy Munoz",
    "Carson Mumford",
    "Derek Kelley",
    "Cullin Park",
    "Daxton Bennick",   # ofta West, kontrollera för 2026
    "Casey Cochran",
    "Hunter Yoder",
    "Jerry Robin",
]

EAST = [
    "Tom Vialle",
    "RJ Hampshire",
    "Jordon Smith",
    "Cameron McAdoo",
    "Nate Thrasher",
    "Max Vohland",
    "Enzo Lopes",
    "Chance Hymas",
    "Pierce Brown",
    "Mitchell Harrison",
    "Stilez Robertson",
    "Preston Kilroy",
    "Talon Hawkins",
    "Nick Romano",
    "Evan Ferry",
]

BOTH = [
    # Lämna tom eller lägg förare du medvetet vill släppa igenom båda coasts på
]

def set_coast(names, coast):
    for name in names:
        r = Rider.query.filter_by(name=name, class_name="250cc").first()
        if r:
            r.coast_250 = coast
            print(f"Set {name} -> {coast}")
        else:
            print(f"[WARN] Hittar inte 250-förare i DB: {name}")

def main():
    with app.app_context():
        set_coast(WEST, "west")
        set_coast(EAST, "east")
        set_coast(BOTH, "both")
        db.session.commit()
        print("KLART. coast_250 uppdaterad för valda 250-förare.")

if __name__ == "__main__":
    main()