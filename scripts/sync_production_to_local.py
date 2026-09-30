#!/usr/bin/env python3
"""
Copy production (Render Postgres) data into local SQLite for testing.

Read-only against production. Requires PRODUCTION_DATABASE_URL in .env.

Usage:
  python scripts/sync_production_to_local.py
  python scripts/sync_production_to_local.py --full
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

# Flask-SQLAlchemy resolves sqlite:///NAME to instance/NAME (do not prefix instance/)
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
    "league_season_archives",
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
    "riders": {"rider_image_data", "bio", "achievements"},
    # users.profile_picture_url included — small JPEG base64, needed for avatars locally
    # leagues.image_data included — few rows, needed for ligabilder locally (Render stores in DB)
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
        return 0

    skip = BLOB_COLUMNS.get(table, set()) if skip_blobs else set()
    cols = [c for c in sorted(prod_cols & local_cols) if c not in skip]
    if not cols:
        return 0

    col_list = ", ".join(_quote_col(c) for c in cols)
    with prod_engine.connect() as conn_prod:
        rows = conn_prod.execute(text(f"SELECT {col_list} FROM {table}")).mappings().all()
    rows = _dedupe_rows(table, [dict(r) for r in rows])

    with local_engine.begin() as conn_local:
        conn_local.execute(text("PRAGMA foreign_keys=OFF"))
        conn_local.execute(text(f"DELETE FROM {table}"))

        if not rows:
            return 0

        placeholders = ", ".join(f":{c}" for c in cols)
        insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
        conn_local.execute(text(insert_sql), [dict(r) for r in rows])
    return len(rows)


def resolve_prod_url() -> str:
    prod_url = (os.getenv("PRODUCTION_DATABASE_URL") or "").strip()
    if not prod_url:
        prod_url = (os.getenv("DATABASE_URL") or "").strip()
    return prod_url


def run_sync(
    *,
    skip_blobs: bool = True,
    app: Any | None = None,
    db: Any | None = None,
    log: bool = True,
) -> dict[str, Any]:
    """
    Copy Render Postgres → local SQLite.

    When app/db are provided (in-process from Flask), reuses that app.
    Otherwise boots main.py against local SQLite (CLI).
    """
    from sqlalchemy import create_engine, text

    prod_url = resolve_prod_url()
    if "postgresql" not in prod_url:
        return {
            "ok": False,
            "error": "PRODUCTION_DATABASE_URL saknas i .env (Render Postgres External URL).",
        }

    try:
        import psycopg2  # noqa: F401
    except ImportError:
        return {
            "ok": False,
            "error": "psycopg2-binary saknas. Kör: pip install psycopg2-binary",
        }

    t0 = time.time()
    local_file = os.path.join(ROOT, "instance", LOCAL_DB_NAME)
    if log:
        print("=" * 60)
        print("Hämtar produktionsdata till lokal SQLite")
        print("  Källa: Render Postgres (read-only)")
        print(f"  Mål:   {local_file}")
        print(f"  Läge:  {'utan stora rider-blobs' if skip_blobs else 'full (inkl. blobs)'}")
        print("=" * 60)

    own_app = app is None
    if own_app:
        os.environ["DATABASE_URL"] = LOCAL_URL
        os.environ.pop("RENDER", None)
        from main import app as flask_app, db as flask_db  # noqa: E402

        app = flask_app
        db = flask_db
    assert app is not None and db is not None

    # Release locks so we can wipe/reload while the local server is running.
    try:
        db.session.remove()
        db.engine.dispose()
    except Exception:
        pass

    prod_engine = create_engine(prod_url, pool_pre_ping=True)
    table_counts: dict[str, int] = {}
    errors: list[str] = []
    total = 0
    comps = results = scores = users = 0

    try:
        with app.app_context():
            db.create_all()
            try:
                from main import _sqlite_add_column_if_missing  # noqa: E402

                _sqlite_add_column_if_missing(
                    "riders", "rider_image_data", "rider_image_data TEXT"
                )
                _sqlite_add_column_if_missing(
                    "users", "password_reset_token", "password_reset_token VARCHAR(64)"
                )
                _sqlite_add_column_if_missing(
                    "users", "password_reset_expires", "password_reset_expires TIMESTAMP"
                )
            except Exception:
                pass

            local_engine = db.engine
            with local_engine.begin() as conn:
                conn.execute(text("PRAGMA foreign_keys=OFF"))
                for table in reversed(SYNC_TABLES):
                    try:
                        conn.execute(text(f"DELETE FROM {table}"))
                    except Exception:
                        pass

            for table in SYNC_TABLES:
                try:
                    n = _copy_table(
                        prod_engine, local_engine, table, skip_blobs=skip_blobs
                    )
                    table_counts[table] = n
                    total += n
                    if log:
                        print(f"  {table}: {n} rader")
                except Exception as exc:
                    msg = f"{table}: {exc}"
                    errors.append(msg)
                    if log:
                        print(f"  {table}: FEL - {exc}")

            comps = db.session.execute(text("SELECT COUNT(*) FROM competitions")).scalar() or 0
            results = (
                db.session.execute(text("SELECT COUNT(*) FROM competition_results")).scalar()
                or 0
            )
            scores = (
                db.session.execute(text("SELECT COUNT(*) FROM competition_scores")).scalar()
                or 0
            )
            users = db.session.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
    finally:
        try:
            prod_engine.dispose()
        except Exception:
            pass

    elapsed = round(time.time() - t0, 1)
    summary = {
        "ok": True,
        "elapsed_sec": elapsed,
        "local_db": local_file,
        "skip_blobs": skip_blobs,
        "rows_copied": total,
        "competitions": int(comps),
        "results": int(results),
        "scores": int(scores),
        "users": int(users),
        "table_counts": table_counts,
        "errors": errors,
        "restart_hint": "Ladda om sidan. Om något ser konstigt ut: starta om lokal server.",
    }
    if log:
        print()
        print("Klart!")
        print(
            f"  Tävlingar: {comps}  |  Resultat: {results}  |  "
            f"Poängrader: {scores}  |  Användare: {users}  ({elapsed}s)"
        )
        if errors:
            print(f"  Varningar: {len(errors)} tabell(er) misslyckades")
        print()
    return summary


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

    result = run_sync(skip_blobs=skip_blobs, log=True)
    if not result.get("ok"):
        print(f"FEL: {result.get('error')}")
        return 1

    print("Nästa steg:")
    print("  1. Kör start_local.bat (eller ladda om om servern redan kör)")
    print("  2. Logga in med samma användarnamn/lösenord som på Render")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
