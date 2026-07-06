"""Copy profile_picture_url from production into local SQLite."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from sqlalchemy import create_engine, text

PROD_URL = os.getenv("PRODUCTION_DATABASE_URL", "").strip()
LOCAL_URL = f"sqlite:///{os.path.join(ROOT, 'instance', 'fantasy_mx_local.db')}"


def main() -> int:
    if "postgresql" not in PROD_URL:
        print("PRODUCTION_DATABASE_URL saknas")
        return 1

    prod = create_engine(PROD_URL)
    local = create_engine(LOCAL_URL)

    with prod.connect() as pc:
        rows = pc.execute(
            text(
                "SELECT id, profile_picture_url FROM users "
                "WHERE profile_picture_url IS NOT NULL AND profile_picture_url != ''"
            )
        ).fetchall()

    updated = 0
    with local.begin() as lc:
        for uid, pic in rows:
            res = lc.execute(
                text("UPDATE users SET profile_picture_url = :pic WHERE id = :id"),
                {"pic": pic, "id": uid},
            )
            updated += res.rowcount

    print(f"Uppdaterade {updated} profilbilder lokalt (fran {len(rows)} i prod)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
