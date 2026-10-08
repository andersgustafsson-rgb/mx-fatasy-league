"""Runtime schema patches (skiva 18).

Moved out of main.py. Boot still calls these via re-exports / init_database.
Do NOT delete these until Alembic covers the same columns on prod.
"""
from __future__ import annotations

from models import SeasonTeamArchive, db


_RIDER_IMAGE_COLUMN_CHECKED = False
_MOTO_COLUMNS_CHECKED = False
_SEASON_TEAM_CREATED_AT_CHECKED = False


def _main():
    """Lazy import for one-shot Din kväll hook still in main."""
    import main as _m

    return _m


def _sqlite_add_column_if_missing(table: str, column: str, ddl: str) -> None:
    """Lightweight schema patch for older local SQLite files."""
    if "sqlite" not in str(db.engine.url):
        return
    rows = db.session.execute(db.text(f"PRAGMA table_info({table})")).fetchall()
    if column in {row[1] for row in rows}:
        return
    db.session.execute(db.text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
    db.session.commit()
    print(f'Added missing column {table}.{column}')

def _ensure_email_opt_out_column() -> None:
    """users.email_opt_out — avregistrering från picks/nyhetsmail."""
    try:
        if "postgresql" in str(db.engine.url):
            result = db.session.execute(
                db.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'users' AND column_name = 'email_opt_out'"
                )
            )
            if not result.fetchone():
                db.session.execute(
                    db.text(
                        "ALTER TABLE users ADD COLUMN email_opt_out BOOLEAN "
                        "NOT NULL DEFAULT FALSE"
                    )
                )
                print("Added missing column users.email_opt_out")
            db.session.commit()
        else:
            _sqlite_add_column_if_missing(
                "users", "email_opt_out", "email_opt_out BOOLEAN DEFAULT 0 NOT NULL"
            )
    except Exception as col_err:
        print(f"Warning: email_opt_out migration skipped: {col_err}")
        db.session.rollback()

def _ensure_racerx_bio_skip_column() -> None:
    """racerx_bio_skip — batch hoppar över namn som saknas på RacerX."""
    try:
        if "postgresql" in str(db.engine.url):
            result = db.session.execute(
                db.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'riders' AND column_name = 'racerx_bio_skip'"
                )
            )
            if not result.fetchone():
                db.session.execute(
                    db.text("ALTER TABLE riders ADD COLUMN racerx_bio_skip VARCHAR(200)")
                )
                print("Added missing column riders.racerx_bio_skip")
            db.session.commit()
        else:
            _sqlite_add_column_if_missing(
                "riders", "racerx_bio_skip", "racerx_bio_skip VARCHAR(200)"
            )
    except Exception as col_err:
        db.session.rollback()
        print(f"Warning: racerx_bio_skip column patch skipped: {col_err}")

def _ensure_rider_bio_sv_columns() -> None:
    """bio_sv / achievements_sv — svensk översättningscache på riders."""
    try:
        if "postgresql" in str(db.engine.url):
            for col in ("bio_sv", "achievements_sv"):
                result = db.session.execute(
                    db.text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'riders' AND column_name = :col"
                    ),
                    {"col": col},
                )
                if not result.fetchone():
                    db.session.execute(db.text(f"ALTER TABLE riders ADD COLUMN {col} TEXT"))
                    print(f"Added missing column riders.{col}")
            db.session.commit()
        else:
            _sqlite_add_column_if_missing("riders", "bio_sv", "bio_sv TEXT")
            _sqlite_add_column_if_missing("riders", "achievements_sv", "achievements_sv TEXT")
    except Exception as col_err:
        db.session.rollback()
        print(f"Warning: riders bio_sv column patch skipped: {col_err}")

def _ensure_season_team_created_at_column() -> None:
    """season_teams.created_at — used so late-built teams get no retroactive race points."""
    global _SEASON_TEAM_CREATED_AT_CHECKED
    if _SEASON_TEAM_CREATED_AT_CHECKED:
        return
    try:
        if "sqlite" in str(db.engine.url):
            _sqlite_add_column_if_missing(
                "season_teams", "created_at", "created_at DATETIME"
            )
        else:
            db.session.execute(
                db.text(
                    "ALTER TABLE season_teams ADD COLUMN IF NOT EXISTS created_at TIMESTAMP"
                )
            )
            db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"ensure season_teams.created_at: {e}")
    _SEASON_TEAM_CREATED_AT_CHECKED = True

def _ensure_rider_image_data_column():
    """Säkerställ att riders.rider_image_data finns (överlever deploy). Kör tyst om kolumnen redan finns."""
    global _RIDER_IMAGE_COLUMN_CHECKED
    if _RIDER_IMAGE_COLUMN_CHECKED:
        return
    try:
        db.session.execute(db.text("ALTER TABLE riders ADD COLUMN IF NOT EXISTS rider_image_data TEXT"))
        db.session.commit()
    except Exception:
        try:
            db.session.execute(db.text("ALTER TABLE riders ADD COLUMN rider_image_data TEXT"))
            db.session.commit()
        except Exception:
            db.session.rollback()
    _RIDER_IMAGE_COLUMN_CHECKED = True

def _ensure_competition_result_moto_columns():
    """Säkerställ moto_1/moto_2 på competition_results (MX import)."""
    global _MOTO_COLUMNS_CHECKED
    if _MOTO_COLUMNS_CHECKED:
        return
    try:
        if "sqlite" in str(db.engine.url):
            _sqlite_add_column_if_missing(
                "competition_results", "moto_1_position", "moto_1_position INTEGER"
            )
            _sqlite_add_column_if_missing(
                "competition_results", "moto_2_position", "moto_2_position INTEGER"
            )
        else:
            db.session.execute(
                db.text("ALTER TABLE competition_results ADD COLUMN IF NOT EXISTS moto_1_position INTEGER")
            )
            db.session.execute(
                db.text("ALTER TABLE competition_results ADD COLUMN IF NOT EXISTS moto_2_position INTEGER")
            )
            db.session.commit()
        _MOTO_COLUMNS_CHECKED = True
    except Exception as e:
        db.session.rollback()
        print(f"Warning: moto column ensure failed: {e}")

def _ensure_app_runtime_flags_table() -> None:
    try:
        db.session.execute(
            db.text(
                """
                CREATE TABLE IF NOT EXISTS app_runtime_flags (
                    flag_key VARCHAR(120) PRIMARY KEY,
                    flag_value TEXT,
                    set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
    try:
        # Older installs may lack flag_value
        bind = db.session.get_bind()
        dialect = (bind.dialect.name if bind is not None else "") or ""
        if dialect == "sqlite":
            cols = {
                r[1]
                for r in db.session.execute(db.text("PRAGMA table_info(app_runtime_flags)")).fetchall()
            }
            if "flag_value" not in cols:
                db.session.execute(db.text("ALTER TABLE app_runtime_flags ADD COLUMN flag_value TEXT"))
                db.session.commit()
        else:
            db.session.execute(
                db.text("ALTER TABLE app_runtime_flags ADD COLUMN IF NOT EXISTS flag_value TEXT")
            )
            db.session.commit()
    except Exception:
        db.session.rollback()

def _ensure_race_recap_table() -> None:
    """Create dismissal table if missing (create_all alone is flaky on some deploys)."""
    try:
        db.create_all()
    except Exception as e:
        print(f"race_recap create_all: {e}")
    try:
        db.session.execute(
            db.text(
                """
                CREATE TABLE IF NOT EXISTS user_race_recap_dismissals (
                    user_id INTEGER NOT NULL,
                    competition_id INTEGER NOT NULL,
                    dismissed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, competition_id)
                )
                """
            )
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"race_recap ensure table: {e}")
    _ensure_app_runtime_flags_table()
    _main()._maybe_auto_reshow_din_kvall_once()

def _ensure_season_team_archives_table() -> None:
    try:
        SeasonTeamArchive.__table__.create(bind=db.engine, checkfirst=True)
    except Exception as e:
        print(f"season_team_archives ensure: {e}")

def _ensure_league_membership_unique() -> None:
    """Dedupe league_memberships and enforce (league_id, user_id) unique (prod was missing it)."""
    from sqlalchemy import inspect, text

    try:
        if not inspect(db.engine).has_table("league_memberships"):
            return
    except Exception:
        return

    # Keep lowest id per (league_id, user_id); drop the rest.
    try:
        dialect = (db.engine.dialect.name or "").lower()
        if dialect == "postgresql":
            deleted = db.session.execute(
                text(
                    """
                    DELETE FROM league_memberships a
                    USING league_memberships b
                    WHERE a.league_id = b.league_id
                      AND a.user_id = b.user_id
                      AND a.id > b.id
                    """
                )
            )
            n = deleted.rowcount or 0
        else:
            deleted = db.session.execute(
                text(
                    """
                    DELETE FROM league_memberships
                    WHERE id NOT IN (
                        SELECT MIN(id) FROM league_memberships
                        GROUP BY league_id, user_id
                    )
                    """
                )
            )
            n = deleted.rowcount or 0
        if n:
            print(f"league_memberships: removed {n} duplicate row(s)")
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"league_memberships dedupe skipped: {e}")
        return

    try:
        insp = inspect(db.engine)
        uniques = {c.get("name") for c in (insp.get_unique_constraints("league_memberships") or [])}
        indexes = {i.get("name") for i in (insp.get_indexes("league_memberships") or [])}
        if "uq_league_user" in uniques or "uq_league_user" in indexes:
            return
        dialect = (db.engine.dialect.name or "").lower()
        if dialect == "postgresql":
            db.session.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_league_user "
                    "ON league_memberships (league_id, user_id)"
                )
            )
        else:
            db.session.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_league_user "
                    "ON league_memberships (league_id, user_id)"
                )
            )
        db.session.commit()
        print("league_memberships: ensured unique index uq_league_user")
    except Exception as e:
        db.session.rollback()
        print(f"league_memberships unique index skipped: {e}")
