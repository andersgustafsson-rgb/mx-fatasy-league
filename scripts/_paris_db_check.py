import os
import sqlite3

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for db in ("fantasy_mx_local.db", "fantasy_mx.db"):
    if not os.path.isfile(db):
        continue
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT id, name, series, phase FROM competitions WHERE name LIKE '%Paris%'"
    ).fetchall()
    print(db, rows)
