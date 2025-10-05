# tools/set_manual_images.py
import sys
import pathlib

# Ensure project root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app, db, Rider  # noqa


def set_image(name: str, rel_path: str):
    """Set image_url for the rider with exact name match."""
    rider = Rider.query.filter(db.func.lower(Rider.name) == name.lower()).first()
    if not rider:
        print(f"[SKIP] Rider not found: {name}")
        return
    rider.image_url = rel_path  # path relative to static/
    db.session.add(rider)
    print(f"[OK] {name} -> {rel_path}")


def main():
    # Map your rider names (as in your DB) to your files under static/
    manual = {
        "Eli Tomac": "riders/eli_tomac.jpg",
        "Jett Lawrence": "riders/jett_lawrence.jpg",
        "Chase Sexton": "riders/chase_sexton.jpg",
        # add more if you want
    }

    with app.app_context():
        for name, rel_path in manual.items():
            set_image(name, rel_path)
        db.session.commit()
        print("[DONE] Manual images saved.")


if __name__ == "__main__":
    main()