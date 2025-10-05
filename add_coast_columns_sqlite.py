# add_coast_columns_sqlite.py
import sqlite3

DB = "instance/fantasy_mx.db"

def add_column(conn, table, column, ddl):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if column in cols:
        print(f"[SKIP] {table}.{column} finns redan")
        return
    print(f"[ADD ] {table}.{column}")
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl};")

def main():
    conn = sqlite3.connect(DB)
    try:
        add_column(conn, "competitions", "coast_250", "TEXT")  # 'east'/'west'/'both'
        add_column(conn, "riders", "coast_250", "TEXT")        # 'east'/'west'/'both'
        conn.commit()
        print("KLART. Kolumner tillagda.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()