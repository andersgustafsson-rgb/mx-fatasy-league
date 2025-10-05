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

# Ensure project root on sys.path so "from app import ..." works
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app, db, Rider  # noqa: E402

CSV_IN = pathlib.Path("data/racerx_riders_2026.csv")
OVR_PATH = pathlib.Path("data/racerx_name_map.csv")
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


def load_overrides() -> dict:
    """Load optional name/number overrides from data/racerx_name_map.csv."""
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
        print("Missing CSV:", CSV_IN)
        print("Run: python tools/scrape_racerx_riders.py first.")
        return

    overrides = load_overrides()

    with app.app_context():
        rows = list(csv.DictReader(CSV_IN.open(encoding="utf-8")))
        scraped_total = len(rows)
        matched = 0
        updated = 0
        misses = []

        # Debug: how many overrides will hit your DB?
        if overrides:
            ok, bad = 0, 0
            for (_, _), ov in overrides.items():
                q = Rider.query.filter(db.func.lower(Rider.name) == ov["name"].lower())
                if ov["number"] is not None:
                    q = q.filter(Rider.rider_number == ov["number"])
                (ok := ok + 1) if q.first() else (bad := bad + 1)
            print(f"[DEBUG] overrides -> DB hits: {ok}, misses: {bad}")

        ALL_DB_NAMES = None  # for fuzzy cache

        for r in rows:
            name = norm_name(r.get("name_guess") or "")
            num_raw = r.get("number_guess")
            num = int(num_raw) if str(num_raw).isdigit() else None
            img = (r.get("img_url") or "").strip()

            # Skip rows that have neither name nor image
            if not name and not img:
                continue

            # Apply overrides if present
            key = (name.lower(), num)
            if key in overrides:
                name = overrides[key]["name"] or name
                tmpnum = overrides[key]["number"]
                num = tmpnum if tmpnum is not None else num

            candidate = None

            # 1) exact (name, number)
            q = Rider.query.filter(db.func.lower(Rider.name) == name.lower())
            if num is not None:
                q = q.filter(Rider.rider_number == num)
            candidate = q.first()

            # 2) exact name only
            if not candidate:
                candidate = Rider.query.filter(
                    db.func.lower(Rider.name) == name.lower()
                ).first()

            # 3) number only (safe if numbers are unique in your DB)
            if not candidate and num is not None:
                candidate = Rider.query.filter(Rider.rider_number == num).first()

            # 4) fuzzy (optional)
            if not candidate and HAS_FUZZY:
                if ALL_DB_NAMES is None:
                    ALL_DB_NAMES = [(rid.id, rid.name) for rid in Rider.query.all()]
                choices = [n for _, n in ALL_DB_NAMES]
                match = process.extractOne(name, choices, scorer=fuzz.WRatio, score_cutoff=90)
                if match:
                    matched_name = match[0]
                    rid_id = next((rid for rid, n in ALL_DB_NAMES if n == matched_name), None)
                    if rid_id:
                        candidate = Rider.query.get(rid_id)

            if not candidate:
                # Record miss for debug report
                misses.append((name, num, img))
                continue

            matched += 1

            # Skip obvious placeholder images
            if img.lower().endswith("post_thumb.png"):
                # Keep the DB match but don't update image_url from a placeholder
                continue

            # Download image and update rider
            try:
                fname = pick_filename(candidate.name, candidate.rider_number, img)
                dest = DEST_DIR / fname
                download_image(img, dest)
                # store path relative to static/
                candidate.image_url = f"riders/{fname}"
                updated += 1
            except Exception as e:
                print("[MISS-DL]", candidate.name, img, e)

        # DEBUG REPORT (before commit)
        print(f"[DEBUG] scraped rows: {scraped_total}")
        print(f"[DEBUG] matched: {matched}, updated images: {updated}, misses: {len(misses)}")
        if misses:
            print("[DEBUG] first 25 misses (name, number, img_url):")
            for m in misses[:25]:
                print("  -", m)

        # Commit DB changes
        db.session.commit()
        print(f"[OK] matched riders: {matched}, updated images: {updated}")
        print("Example web path to display: url_for('static', filename=rider.image_url)")


if __name__ == "__main__":
    main()