"""Inspect AMA tippa duplicates (same name in 450cc + 250cc) and their FK usage."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import inspect, text

from main import app
from models import Rider, db

NAMES = [
    "Cooper Webb",
    "Devin Simonson",
    "Marshal Weltin",
    "Valentin Guillod",
    "Lorenzo Locurcio",
    "Mark Fineis",
    "Justin Rodbell",
    "Jeremy Hand",
    "Matti Jorgensen",
]


def main() -> None:
    with app.app_context():
        insp = inspect(db.engine)
        rider_cols: list[tuple[str, str]] = []
        for t in insp.get_table_names():
            for col in insp.get_columns(t):
                cname = col["name"]
                if cname.endswith("rider_id") or cname in ("rider_id",):
                    rider_cols.append((t, cname))

        print("rider_id columns:", rider_cols)
        print()
        for name in NAMES:
            rows = (
                Rider.query.filter(Rider.class_name.in_(["450cc", "250cc"]))
                .filter(Rider.name.ilike(name))
                .order_by(Rider.class_name)
                .all()
            )
            if len(rows) < 2:
                first, last = name.split(" ", 1)
                rows = (
                    Rider.query.filter(Rider.class_name.in_(["450cc", "250cc"]))
                    .filter(Rider.name.ilike(f"%{last}%"))
                    .filter(Rider.name.ilike(f"%{first}%"))
                    .order_by(Rider.class_name)
                    .all()
                )
            print(f"=== {name} ===")
            for r in rows:
                counts = {}
                for table, col in rider_cols:
                    try:
                        n = db.session.execute(
                            text(f"SELECT COUNT(*) FROM {table} WHERE {col} = :id"),
                            {"id": r.id},
                        ).scalar()
                    except Exception as e:
                        counts[f"{table}.{col}"] = f"ERR {e}"
                        continue
                    if n:
                        counts[f"{table}.{col}"] = int(n)
                print(
                    f"  id={r.id} {r.class_name} #{r.rider_number} "
                    f"price={r.price} brand={r.bike_brand}"
                )
                print(f"    refs={counts or '(none)'}")
            print()


if __name__ == "__main__":
    main()
