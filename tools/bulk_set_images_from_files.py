# tools/bulk_set_images_from_files.py
import re
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app, db, Rider  # noqa

IMAGES_DIR = ROOT / "static" / "riders"

def norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace(".", "")
    s = re.sub(r"[\s_]+", " ", s)         # ersätt underscore till space
    s = re.sub(r"\s+", " ", s)            # collapse whitespace
    return s

def main():
    if not IMAGES_DIR.exists():
        print("[ERR] static/riders saknas:", IMAGES_DIR)
        return

    files = [p for p in IMAGES_DIR.iterdir() if p.is_file()]
    if not files:
        print("[INFO] Inga filer i static/riders")
        return

    updated = 0
    skipped = 0

    with app.app_context():
        riders = Rider.query.all()
        # indexera DB-riders: number -> rid, samt normaliserat namn -> rid
        by_number = {}
        by_name = {}
        for rid in riders:
            if rid.rider_number:
                by_number[int(rid.rider_number)] = rid
            by_name[norm(rid.name)] = rid

        for fp in files:
            rel = f"riders/{fp.name}"  # relativ till static/
            fname = fp.stem  # filnamn utan extension
            # 1) försök hitta ledande nummer: t.ex. "3_eli_tomac" -> 3
            m = re.match(r"^(\d{1,3})[_\s-]", fname)
            candidate = None
            if m:
                try:
                    num = int(m.group(1))
                    candidate = by_number.get(num)
                except Exception:
                    candidate = None

            # 2) om ej hittad via nummer, matcha på namn
            if not candidate:
                # ta bort ledande nummer + separator om det finns
                tmp = re.sub(r"^\d{1,3}[_\s-]+", "", fname)
                nm = norm(tmp)
                candidate = by_name.get(nm)
                if not candidate:
                    # mer tolerant: ta bara bokstäver och mellanslag
                    nm2 = norm(re.sub(r"[^a-z0-9\s]", "", tmp))
                    candidate = by_name.get(nm2)

            if not candidate:
                print(f"[SKIP] Ingen match för fil: {fp.name}")
                skipped += 1
                continue

            # sätt image_url
            candidate.image_url = rel
            db.session.add(candidate)
            updated += 1
            print(f"[OK] {candidate.name} -> {rel}")

        db.session.commit()
        print(f"[DONE] Updated: {updated}, skipped: {skipped}")

if __name__ == "__main__":
    main()