from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import text

from main import app
from models import db

# keep_id based on Racer X current class (Oct 2026)
PAIRS = [
    ("Cooper Webb", 463, 527, "450"),  # keep 450, drop 250
    ("Devin Simonson", 750, 583, "450"),
    ("Marshal Weltin", 581, 475, "250"),  # RX: 250
    ("Valentin Guillod", 662, 409, "450"),
    ("Lorenzo Locurcio", 626, 420, "450"),
    ("Mark Fineis", 776, 418, "450"),
    ("Justin Rodbell", 492, 576, "450"),
    ("Jeremy Hand", 749, 582, "450"),
    ("Matti Jorgensen", 817, 552, "450"),
]


def main() -> None:
    with app.app_context():
        for name, keep, drop, cls in PAIRS:
            print(f"=== {name} (RX {cls}) keep={keep} drop={drop} ===")
            for rid, label in ((keep, "KEEP"), (drop, "DROP")):
                rows = db.session.execute(
                    text(
                        """
                        SELECT c.id, c.name, c.series, c.event_date,
                               cr.position, cr."class" AS result_class
                        FROM competition_results cr
                        JOIN competitions c ON c.id = cr.competition_id
                        WHERE cr.rider_id = :rid
                        ORDER BY c.event_date
                        """
                    ),
                    {"rid": rid},
                ).fetchall()
                print(f"  {label} id={rid} results={len(rows)}")
                for r in rows[:10]:
                    print(
                        f"    {r.event_date} {r.series} {r.name} "
                        f"pos={r.position} class={r.result_class}"
                    )
                if len(rows) > 10:
                    print(f"    ... +{len(rows) - 10} more")
            print()


if __name__ == "__main__":
    main()
