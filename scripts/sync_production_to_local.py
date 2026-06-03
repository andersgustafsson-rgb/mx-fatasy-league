#!/usr/bin/env python3
"""
Copy production (Render Postgres) data into local SQLite for testing.

Read-only against production. Requires PRODUCTION_DATABASE_URL in .env.

Usage:
  python scripts/sync_production_to_local.py
  python scripts/sync_production_to_local.py --skip-blobs
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

# Same path as start_local.bat (relative to project root)
LOCAL_DB_NAME = "fantasy_mx_local.db"
LOCAL_URL = f"sqlite:///{LOCAL_DB_NAME}"

# Insert order respects foreign keys
SYNC_TABLES = [
    "series",
    "users",
    "riders",
    "global_simulation",
    "competitions",
    "season_teams",
    "season_team_riders",
    "season_team_class_promotions",
    "leagues",
    "league_memberships",
    "league_requests",
    "competition_rider_status",
    "competition_results",
    "competition_images",
    "holeshot_results",
    "race_picks",
    "holeshot_picks",
    "wildcard_picks",
    "picks_snapshots",
    "competition_scores",
    "leaderboard_history",
    "bulletin_posts",
    "bulletin_reactions",
    "cross_dino_highscores",
    "finished_series_stats",
    "admin_announcements",
    "user_announcement_dismissals",
    "message_threads",
    "messages",
    "inbox_notifications",
]

BLOB_COLUMNS = {
    "users": {"profile_picture_url"},
    "riders": {"rider_image_data", "bio", "achievements"},
    "leagues": {"image_data"},
}

# Prod has occasional duplicate rows; keep newest by primary key when copying
DEDUPE_KEYS: dict[str, tuple[str, ...]] = {
    "league_memberships": ("league_id", "user_id"),
    "competition_results": ("competition_id", "rider_id"),
}

DEDUPE_PK: dict[str, str] = {
    "league_memberships": "id",
    "competition_results": "result_id",
}


def _dedupe_rows(table: str, rows: list[dict]) -> list[dict]:
    keys = DEDUPE_KEYS.get(table)
    if not keys or not rows:
        return rows
    pk = DEDUPE_PK.get(table, "id")
    best: dict[tuple, dict] = {}
    for row in rows:
        d = dict(row)
        key = tuple(d.get(k) for k in keys)
        prev = best.get(key)
        if prev is None or int(d.get(pk) or 0) >= int(prev.get(pk) or 0):
            best[key] = d
    return list(best.values())


def _quote_col(name: str) -> str:
    return f'"{name}"' if name == "class" else name


def _table_columns(bind, table: str) -> set[str]:
    from sqlalchemy import inspect

    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _copy_table(prod_engine, local_engine, table: str, *, skip_blobs: bool) -> int:
    from sqlalchemy import text

    prod_cols = _table_columns(prod_engine, table)
    local_cols = _table_columns(local_engine, table)
    if not prod_cols or not local_cols:
        print(f"  {table}: hoppad over (saknas i prod eller lokalt)")
        return 0

    skip = BLOB_COLUMNS.get(table, set()) if skip_blobs else set()
    cols = [c for c in sorted(prod_cols & local_cols) if c not in skip]
    if not cols:
        print(f"  {table}: inga gemensamma kolumner")
        return 0

    col_list = ", ".join(_quote_col(c) for c in cols)
    with prod_engine.connect() as conn_prod:
        rows = conn_prod.execute(text(f"SELECT {col_list} FROM {table}")).mappings().all()
    rows = _dedupe_rows(table, [dict(r) for r in rows])

    with local_engine.begin() as conn_local:
        conn_local.execute(text("PRAGMA foreign_keys=OFF"))
        conn_local.execute(text(f"DELETE FROM {table}"))

        if not rows:
            print(f"  {table}: 0 rader")
            return 0

        placeholders = ", ".join(f":{c}" for c in cols)
        insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
        conn_local.execute(text(insert_sql), [dict(r) for r in rows])
    print(f"  {table}: {len(rows)} rader")
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Render Postgres -> local SQLite")
    parser.add_argument(
        "--skip-blobs",
        action="store_true",
        default=True,
        help="Skip large text/blob columns (default: on, faster)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Include profile images and rider blobs (slower)",
    )
    args = parser.parse_args()
    skip_blobs = args.skip_blobs and not args.full

    prod_url = (os.getenv("PRODUCTION_DATABASE_URL") or "").strip()
    if not prod_url:
        prod_url = (os.getenv("DATABASE_URL") or "").strip()
    if "postgresql" not in prod_url:
        print("FEL: Satt PRODUCTION_DATABASE_URL i .env till Render Postgres-URL.")
        print("     Render -> din PostgreSQL -> External Database URL")
        print("     Exempel:")
        print("     PRODUCTION_DATABASE_URL=postgresql://user:pass@host/dbname")
        return 1

    try:
        from sqlalchemy import create_engine
    except ImportError:
        print("FEL: sqlalchemy saknas. Kor installera_venv.bat")
        return 1

    try:
        import psycopg2  # noqa: F401
    except ImportError:
        print("FEL: psycopg2-binary saknas.")
        print("  .venv\\Scripts\\python.exe -m pip install psycopg2-binary")
        return 1

    print("=" * 60)
    print("Hamtar produktionsdata till lokal SQLite")
    print("  Kalla: Render Postgres (read-only)")
    print(f"  Mal:   {os.path.join(ROOT, LOCAL_DB_NAME)}")
    if skip_blobs:
        print("  Lage:  utan stora bild-blobs (snabbare)")
    print("=" * 60)

    prod_engine = create_engine(prod_url, pool_pre_ping=True)

    # Ensure local schema exists (must set env before importing main)
    os.environ["DATABASE_URL"] = LOCAL_URL
    os.environ.pop("RENDER", None)
    from main import app, db  # noqa: E402

    with app.app_context():
        db.create_all()
        from main import _sqlite_add_column_if_missing  # noqa: E402

        _sqlite_add_column_if_missing("riders", "rider_image_data", "rider_image_data TEXT")
        _sqlite_add_column_if_missing(
            "users", "password_reset_token", "password_reset_token VARCHAR(64)"
        )
        _sqlite_add_column_if_missing(
            "users", "password_reset_expires", "password_reset_expires TIMESTAMP"
        )

        local_engine = db.engine
        from sqlalchemy import text

        with local_engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            for table in reversed(SYNC_TABLES):
                try:
                    conn.execute(text(f"DELETE FROM {table}"))
                except Exception:
                    pass

        total = 0
        for table in SYNC_TABLES:
            try:
                total += _copy_table(prod_engine, local_engine, table, skip_blobs=skip_blobs)
            except Exception as exc:
                print(f"  {table}: FEL - {exc}")

        from sqlalchemy import text

        comps = db.session.execute(text("SELECT COUNT(*) FROM competitions")).scalar() or 0
        results = db.session.execute(text("SELECT COUNT(*) FROM competition_results")).scalar() or 0
        scores = db.session.execute(text("SELECT COUNT(*) FROM competition_scores")).scalar() or 0
        users = db.session.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0

    print()
    print("Klart!")
    print(f"  Tavlingar: {comps}  |  Resultat: {results}  |  Poangrader: {scores}  |  Anvandare: {users}")
    print()
    print("Nasta steg:")
    print("  1. Kor start_local.bat")
    print("  2. Logga in med samma anvandarnamn/losenord som pa Render (t.ex. spliffan)")
    print("  3. Testa Mina poang / poang-modalen")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
