import re
from datetime import datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

from app import app, db, Competition

BASE = "https://www.supercrosslive.com"
URL  = "https://www.supercrosslive.com/tickets/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\(.*?\)", "", s)         # ta bort parenteser, t.ex. (Triple Crown)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s

def parse_date_guess(text: str) -> datetime | None:
    # Försök hitta t.ex. "Jan 3, 2026" / "January 3, 2026"
    m = re.search(r"([A-Za-z]{3,9}\s+\d{1,2},\s*2026)", text)
    if not m:
        return None
    raw = m.group(1).strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    return None

def collect_2026_candidates():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    events = []
    # Heuristik: leta efter länkar/kort med eventnamn; sidor ändras ofta, så vi plockar breda träffar
    for a in soup.select("a[href]"):
        name_text = " ".join(a.get_text(" ", strip=True).split())
        if not name_text:
            continue

        # vi vill ha 2026‑träffar eller kända SX‑orter
        if "2026" not in name_text and not re.search(
            r"(Anaheim|San\s*Francisco|San\s*Diego|Detroit|Glendale|Arlington|Birmingham|Daytona|Indianapolis|Seattle|St\.?\s*Louis|Foxborough|Nashville|Philadelphia|Denver|Salt\s*Lake\s*City)",
            name_text, re.I
        ):
            continue

        # försök hitta datum i nära text (parent/siblings)
        date_dt = None
        for node in (a, a.parent, a.find_next_sibling(), a.find_previous_sibling()):
            if not node:
                continue
            dt = parse_date_guess(node.get_text(" ", strip=True))
            if dt:
                date_dt = dt
                break

        events.append({
            "name": name_text,
            "date": date_dt,   # kan vara None
        })

    # Rensa dubbletter (på namn), välj första med datum
    uniq = {}
    for e in events:
        key = slugify(e["name"])
        if key not in uniq or (e["date"] and not uniq[key]["date"]):
            uniq[key] = e
    return list(uniq.values())

def main():
    candidates = collect_2026_candidates()
    if not candidates:
        print("Inga kandidater hittades – justera selektorer/heuristik.")
        return

    print(f"Hittade {len(candidates)} kandidater från tickets-sidan.")
    updated = 0

    with app.app_context():
        comps = Competition.query.filter_by(series="SX").all()
        comp_by_slug = {slugify(c.name): c for c in comps}

        for cand in candidates:
            s = slugify(cand["name"])
            comp = comp_by_slug.get(s)

            # Fuzzy fallback: slug delmängd åt båda håll
            if not comp:
                for k, v in comp_by_slug.items():
                    if k in s or s in k:
                        comp = v
                        break

            if not comp:
                print(f"[MISS] {cand['name']}")
                continue

            if cand["date"]:
                old = comp.event_date
                comp.event_date = cand["date"].date()
                db.session.add(comp)
                updated += 1
                print(f"[OK] {comp.name}: {old} -> {comp.event_date}")
            else:
                print(f"[NO DATE] {cand['name']} (ingen datum hittat nära namnet)")

        db.session.commit()

    print(f"Klart: uppdaterade datum för {updated} SX‑tävlingar.")

if __name__ == "__main__":
    main()