"""
Import WSX rider images from RacerX CSV data.
Matches WSX riders (wsx_sx1, wsx_sx2) against RacerX scraped data.
"""
import os
import re
import csv
import sys
import pathlib
import requests
from werkzeug.utils import secure_filename

# Optional fuzzy support (safe if not installed)
try:
    from rapidfuzz import process, fuzz
    HAS_FUZZY = True
except Exception:
    HAS_FUZZY = False

# Ensure project root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from models import db, Rider

CSV_IN = pathlib.Path("data/racerx_riders_2026.csv")
DEST_DIR = pathlib.Path("static/riders")
DEST_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def norm_name(s: str) -> str:
    """Normalize rider names: trim, collapse whitespace, remove dots."""
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace(".", "")
    return s


def pick_filename(name: str, number: int | None, url: str) -> str:
    """Build a stable local filename: '<number>_<name>.ext' or '<name>.ext'."""
    base = norm_name(name).lower().replace(" ", "_")
    if number:
        base = f"{number}_{base}"
    path = url.split("?", 1)[0]
    ext = os.path.splitext(path)[1] or ".jpg"
    return secure_filename(base + ext)


def download_image(url: str, dest_path: pathlib.Path):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    dest_path.write_bytes(resp.content)


def main():
    if not CSV_IN.exists():
        print(f"[ERROR] Missing CSV: {CSV_IN}")
        print("Run: python tools/scrape_racerx_riders.py first.")
        return

    print(f"[INFO] Starting WSX image import from {CSV_IN}")
    
    app = create_app()
    with app.app_context():
        # Load RacerX data into a dict by name (normalized)
        racerx_data = {}
        with CSV_IN.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = norm_name(row.get("name_guess") or "")
                num_raw = row.get("number_guess")
                num = int(num_raw) if str(num_raw).isdigit() else None
                img = (row.get("img_url") or "").strip()
                
                if not name or not img:
                    continue
                
                # Skip placeholder images
                if img.lower().endswith("post_thumb.png"):
                    continue
                
                # Store by normalized name (lowercase)
                key = name.lower()
                if key not in racerx_data:
                    racerx_data[key] = []
                racerx_data[key].append({
                    "name": name,
                    "number": num,
                    "img_url": img
                })

        print(f"[INFO] Loaded {len(racerx_data)} unique riders from RacerX CSV")

        # Get all WSX riders from database
        wsx_riders = Rider.query.filter(
            db.or_(
                Rider.class_name.in_(['wsx_sx1', 'wsx_sx2']),
                Rider.series_participation == 'wsx'
            )
        ).all()

        print(f"[INFO] Found {len(wsx_riders)} WSX riders in database")

        matched = 0
        updated = 0
        misses = []

        # Build list of all DB rider names for fuzzy matching
        ALL_DB_NAMES = None
        if HAS_FUZZY:
            ALL_DB_NAMES = [(rid.id, rid.name) for rid in Rider.query.all()]

        for rider in wsx_riders:
            name = norm_name(rider.name)
            key = name.lower()

            # Find matching image in RacerX data
            match_data = None

            # 1) Exact name match (case-insensitive)
            if key in racerx_data:
                candidates = racerx_data[key]
                # Prefer exact number match if available
                if rider.rider_number:
                    for cand in candidates:
                        if cand["number"] == rider.rider_number:
                            match_data = cand
                            break
                # Otherwise take first match
                if not match_data and candidates:
                    match_data = candidates[0]

            # 2) Try fuzzy match on RacerX data keys
            if not match_data and HAS_FUZZY:
                racerx_keys = list(racerx_data.keys())
                fuzzy_match = process.extractOne(
                    key, racerx_keys, scorer=fuzz.WRatio, score_cutoff=90
                )
                if fuzzy_match:
                    matched_key = fuzzy_match[0]
                    candidates = racerx_data[matched_key]
                    # Prefer number match
                    if rider.rider_number:
                        for cand in candidates:
                            if cand["number"] == rider.rider_number:
                                match_data = cand
                                break
                    if not match_data and candidates:
                        match_data = candidates[0]

            if not match_data:
                misses.append((rider.name, rider.rider_number, rider.class_name))
                continue

            matched += 1
            print(f"[MATCH] {rider.name} (#{rider.rider_number}, {rider.class_name}) -> {match_data['name']} (#{match_data['number']})")

            # Skip if rider already has an image (unless it's a placeholder)
            if rider.image_url and not rider.image_url.endswith("post_thumb.png"):
                print(f"[SKIP] {rider.name} already has image: {rider.image_url}")
                continue

            # Download image and update rider
            try:
                fname = pick_filename(rider.name, rider.rider_number, match_data["img_url"])
                dest = DEST_DIR / fname
                
                # Skip if file already exists
                if dest.exists():
                    print(f"[SKIP] Image already exists: {fname}")
                else:
                    print(f"[DOWNLOAD] Downloading {match_data['img_url']}...")
                    download_image(match_data["img_url"], dest)
                    print(f"[OK] {rider.name} -> {fname}")
                
                # Update database
                rider.image_url = f"riders/{fname}"
                updated += 1
                print(f"[DB] Updated {rider.name}.image_url = riders/{fname}")
            except Exception as e:
                print(f"[ERROR] Failed to download for {rider.name}: {e}")

        # DEBUG REPORT
        print(f"\n[DEBUG] WSX riders processed: {len(wsx_riders)}")
        print(f"[DEBUG] Matched: {matched}, Updated images: {updated}, Misses: {len(misses)}")
        
        if misses:
            print("\n[DEBUG] First 25 misses (name, number, class):")
            for m in misses[:25]:
                print(f"  - {m[0]} (#{m[1]}, {m[2]})")

        # Commit DB changes
        db.session.commit()
        print(f"\n[OK] Matched: {matched}, Updated images: {updated}")


if __name__ == "__main__":
    main()

