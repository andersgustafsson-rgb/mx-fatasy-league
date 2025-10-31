"""
Import WSX rider images from scraped CSV into database.
Similar to import_racerx_images.py but for WSX riders.
"""
import os
import re
import csv
import sys
import pathlib
import requests
from werkzeug.utils import secure_filename

try:
    from rapidfuzz import process, fuzz
    HAS_FUZZY = True
except Exception:
    HAS_FUZZY = False

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from models import db, Rider  # noqa: E402

CSV_IN = pathlib.Path("data/wsx_riders_2025.csv")
OVR_PATH = pathlib.Path("data/wsx_name_map.csv")  # Optional overrides
DEST_DIR = pathlib.Path("static/riders")
DEST_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

def norm_name(s: str) -> str:
    """Normalize rider names."""
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace(".", "")
    return s

def pick_filename(name: str, number: int | None, url: str) -> str:
    """Build filename: '<number>_<name>.ext' or '<name>.ext'."""
    base = norm_name(name).lower().replace(" ", "_")
    if number:
        base = f"{number}_{base}"
    path = url.split("?", 1)[0]
    ext = os.path.splitext(path)[1] or ".jpg"
    return secure_filename(base + ext)

def load_overrides() -> dict:
    """Load optional name/number overrides."""
    ovr = {}
    if OVR_PATH.exists():
        with OVR_PATH.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                ng = (row.get("name_guess") or "").strip().lower()
                gg = (row.get("number_guess") or "").strip()
                nnum = int(gg) if gg.isdigit() else None
                ovr[(ng, nnum)] = {
                    "name": norm_name(row.get("db_name_override") or ""),
                    "number": (
                        int(row["db_number_override"])
                        if str(row.get("db_number_override", "")).isdigit()
                        else None
                    ),
                }
    return ovr

def download_image(url: str, dest_path: pathlib.Path):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    dest_path.write_bytes(resp.content)

def main():
    if not CSV_IN.exists():
        print(f"Missing CSV: {CSV_IN}")
        print("Run: python tools/scrape_wsx_riders.py first.")
        return

    overrides = load_overrides()

    app = create_app()
    with app.app_context():
        rows = list(csv.DictReader(CSV_IN.open(encoding="utf-8")))
        scraped_total = len(rows)
        matched = 0
        updated = 0
        misses = []

        if overrides:
            ok, bad = 0, 0
            for (_, _), ov in overrides.items():
                q = Rider.query.filter(db.func.lower(Rider.name) == ov["name"].lower())
                if ov["number"] is not None:
                    q = q.filter(Rider.rider_number == ov["number"])
                (ok := ok + 1) if q.first() else (bad := bad + 1)
            print(f"[DEBUG] overrides -> DB hits: {ok}, misses: {bad}")

        ALL_DB_NAMES = None

        for r in rows:
            name = norm_name(r.get("name_guess") or "")
            num_raw = r.get("number_guess")
            num = int(num_raw) if str(num_raw).isdigit() else None
            img = (r.get("img_url") or "").strip()

            if not name and not img:
                continue

            # Apply overrides
            key = (name.lower(), num)
            if key in overrides:
                name = overrides[key]["name"] or name
                tmpnum = overrides[key]["number"]
                num = tmpnum if tmpnum is not None else num

            candidate = None

            # Match by WSX class names (wsx_sx1, wsx_sx2) or series_participation='wsx'
            # 1) exact (name, number)
            q = Rider.query.filter(db.func.lower(Rider.name) == name.lower())
            if num is not None:
                q = q.filter(Rider.rider_number == num)
            # Prefer WSX riders
            wsx_riders = q.filter(
                db.or_(
                    Rider.class_name.in_(['wsx_sx1', 'wsx_sx2']),
                    Rider.series_participation == 'wsx',
                    Rider.classes.contains('wsx_sx1'),
                    Rider.classes.contains('wsx_sx2')
                )
            ).all()
            if wsx_riders:
                candidate = wsx_riders[0]
            else:
                candidate = q.first()

            # 2) exact name only (with WSX preference)
            if not candidate:
                wsx_by_name = Rider.query.filter(
                    db.func.lower(Rider.name) == name.lower()
                ).filter(
                    db.or_(
                        Rider.class_name.in_(['wsx_sx1', 'wsx_sx2']),
                        Rider.series_participation == 'wsx'
                    )
                ).first()
                if wsx_by_name:
                    candidate = wsx_by_name
                else:
                    candidate = Rider.query.filter(
                        db.func.lower(Rider.name) == name.lower()
                    ).first()

            # 3) number only (if unique)
            if not candidate and num is not None:
                wsx_by_num = Rider.query.filter(
                    Rider.rider_number == num
                ).filter(
                    db.or_(
                        Rider.class_name.in_(['wsx_sx1', 'wsx_sx2']),
                        Rider.series_participation == 'wsx'
                    )
                ).first()
                if wsx_by_num:
                    candidate = wsx_by_num
                else:
                    candidate = Rider.query.filter(Rider.rider_number == num).first()

            # 4) fuzzy (optional)
            if not candidate and HAS_FUZZY:
                if ALL_DB_NAMES is None:
                    # Prefer WSX riders in fuzzy search
                    wsx_riders_all = Rider.query.filter(
                        db.or_(
                            Rider.class_name.in_(['wsx_sx1', 'wsx_sx2']),
                            Rider.series_participation == 'wsx'
                        )
                    ).all()
                    ALL_DB_NAMES = [(rid.id, rid.name) for rid in wsx_riders_all]
                    ALL_DB_NAMES += [(rid.id, rid.name) for rid in Rider.query.filter(
                        ~db.or_(
                            Rider.class_name.in_(['wsx_sx1', 'wsx_sx2']),
                            Rider.series_participation == 'wsx'
                        )
                    ).all()]
                choices = [n for _, n in ALL_DB_NAMES]
                match = process.extractOne(name, choices, scorer=fuzz.WRatio, score_cutoff=90)
                if match:
                    matched_name = match[0]
                    rid_id = next((rid for rid, n in ALL_DB_NAMES if n == matched_name), None)
                    if rid_id:
                        candidate = Rider.query.get(rid_id)

            if not candidate:
                misses.append((name, num, img))
                continue

            matched += 1

            # Skip placeholder images
            if img and ("placeholder" in img.lower() or "logo" in img.lower() or img.lower().endswith("post_thumb.png")):
                continue

            # Download and update
            if img:
                try:
                    fname = pick_filename(candidate.name, candidate.rider_number, img)
                    dest = DEST_DIR / fname
                    download_image(img, dest)
                    candidate.image_url = f"riders/{fname}"
                    updated += 1
                except Exception as e:
                    print("[MISS-DL]", candidate.name, img, e)

        print(f"[DEBUG] scraped rows: {scraped_total}")
        print(f"[DEBUG] matched: {matched}, updated images: {updated}, misses: {len(misses)}")
        if misses:
            print("[DEBUG] first 25 misses (name, number, img_url):")
            for m in misses[:25]:
                print("  -", m)

        db.session.commit()
        print(f"[OK] matched riders: {matched}, updated images: {updated}")

if __name__ == "__main__":
    main()

