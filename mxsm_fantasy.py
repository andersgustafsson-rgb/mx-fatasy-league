"""MXSM (Motocross SM) scaffold — 2026 sandbox roster/calendar, 2027 public UC.

Public tippa locked until MXSM_PUBLIC_PLAY. Admins can seed + test locally.

Per-race classes via Competition.tippa_classes (CSV of class codes).
Scoring ignores heat count (2- vs 3-heat) — overall result only.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from models import Competition, Rider, Series, db

# Flip when ready for public tippa (2027 season).
MXSM_PUBLIC_PLAY = False

SERIES_CODE = "MXSM"

CLASS_MX1 = "mxsm_mx1"
CLASS_MX2 = "mxsm_mx2"
CLASS_U17 = "mxsm_u17"

CLASSES_MX = (CLASS_MX1, CLASS_MX2)
CLASSES_ALL = (CLASS_MX1, CLASS_MX2, CLASS_U17)
DEFAULT_TIPPA_CLASSES = ",".join(CLASSES_MX)

ADMIN_TEST_RACE_NAME = "MXSM Admin Test"

_ROOT = Path(__file__).resolve().parent
_ROSTER_CSV = _ROOT / "data" / "mxsm_2026_roster.csv"

# Official Svemo 2026 MXSM dates (main tippa day = race day / sista dagen vid 2-dagars).
# Classes from organiser entry lists (user 2026 scheme).
# (name, event_date, tippa_classes_tuple)
_MXSM_2026_CALENDAR: list[tuple[str, date, tuple[str, ...]]] = [
    ("MXSM Landskrona", date(2026, 5, 2), CLASSES_ALL),  # 1–2 maj
    ("MXSM Linköping", date(2026, 5, 17), CLASSES_ALL),  # 16–17 maj
    ("MXSM Tibro", date(2026, 6, 14), CLASSES_MX),  # 14 juni — ingen U17
    ("MXSM Varberg", date(2026, 7, 12), CLASSES_ALL),  # 12 juli
    ("MXSM Ulricehamn", date(2026, 8, 9), CLASSES_ALL),  # 8–9 aug
    ("MXSM Göta", date(2026, 8, 30), CLASSES_ALL),  # 29–30 aug
    ("MXSM Uddevalla", date(2026, 9, 19), CLASSES_ALL),  # 19 sep
]

_TIPPA_CLASSES_COLUMN_READY = False


def is_mxsm_series(series: str | None) -> bool:
    return (series or "").strip().upper() == SERIES_CODE


def mxsm_public_play_enabled() -> bool:
    return bool(MXSM_PUBLIC_PLAY)


def mxsm_user_can_play(*, is_admin: bool) -> bool:
    """Public tippa locked until MXSM_PUBLIC_PLAY; admins always can test."""
    return bool(is_admin) or mxsm_public_play_enabled()


def ensure_mxsm_tippa_classes_column() -> None:
    """Soft-add competitions.tippa_classes (CSV: mxsm_mx1,mxsm_mx2,mxsm_u17)."""
    global _TIPPA_CLASSES_COLUMN_READY
    if _TIPPA_CLASSES_COLUMN_READY:
        return
    try:
        url = str(db.engine.url)
        if "postgresql" in url:
            exists = db.session.execute(
                db.text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'competitions' AND column_name = 'tippa_classes'"
                )
            ).fetchone()
            if not exists:
                db.session.execute(
                    db.text(
                        "ALTER TABLE competitions "
                        "ADD COLUMN tippa_classes VARCHAR(64)"
                    )
                )
                db.session.commit()
                print("Added competitions.tippa_classes")
        elif "sqlite" in url:
            rows = db.session.execute(db.text("PRAGMA table_info(competitions)")).fetchall()
            if "tippa_classes" not in {r[1] for r in rows}:
                db.session.execute(
                    db.text("ALTER TABLE competitions ADD COLUMN tippa_classes VARCHAR(64)")
                )
                db.session.commit()
                print("Added competitions.tippa_classes")
        _TIPPA_CLASSES_COLUMN_READY = True
    except Exception as e:
        db.session.rollback()
        print(f"ensure_mxsm_tippa_classes_column: {e}")


def normalize_tippa_classes(raw: str | None) -> tuple[str, ...]:
    if not (raw or "").strip():
        return CLASSES_MX
    parts = []
    for p in (raw or "").replace(";", ",").split(","):
        key = p.strip().lower()
        if not key:
            continue
        # Allow short aliases in admin/seed paste
        alias = {
            "mx1": CLASS_MX1,
            "mx2": CLASS_MX2,
            "u17": CLASS_U17,
            "125u17": CLASS_U17,
            CLASS_MX1: CLASS_MX1,
            CLASS_MX2: CLASS_MX2,
            CLASS_U17: CLASS_U17,
        }.get(key)
        if alias and alias not in parts:
            parts.append(alias)
    return tuple(parts) if parts else CLASSES_MX


def tippa_classes_csv(classes: tuple[str, ...] | list[str]) -> str:
    return ",".join(classes)


def get_mxsm_tippa_classes(competition: Competition | None) -> tuple[str, ...]:
    """Which classes are tippable for this MXSM race weekend."""
    if competition is None:
        return CLASSES_MX
    raw = None
    if hasattr(competition, "tippa_classes"):
        raw = getattr(competition, "tippa_classes", None)
    if not raw:
        # Fallback: look up by name in 2026 calendar seed
        name = (getattr(competition, "name", None) or "").strip()
        for cal_name, _dt, classes in _MXSM_2026_CALENDAR:
            if name == cal_name or name.endswith(cal_name.replace("MXSM ", "")):
                return classes
        if name == ADMIN_TEST_RACE_NAME:
            return CLASSES_ALL
    return normalize_tippa_classes(raw)


def competition_has_class(competition: Competition | None, class_name: str) -> bool:
    return class_name in get_mxsm_tippa_classes(competition)


def competition_has_u17(competition: Competition | None) -> bool:
    return competition_has_class(competition, CLASS_U17)


def competition_has_mx(competition: Competition | None) -> bool:
    classes = get_mxsm_tippa_classes(competition)
    return CLASS_MX1 in classes or CLASS_MX2 in classes


def set_competition_tippa_classes(
    competition: Competition, classes: tuple[str, ...] | list[str]
) -> None:
    ensure_mxsm_tippa_classes_column()
    csv_val = tippa_classes_csv(tuple(classes))
    try:
        competition.tippa_classes = csv_val  # type: ignore[attr-defined]
    except Exception:
        db.session.execute(
            db.text("UPDATE competitions SET tippa_classes = :v WHERE id = :id"),
            {"v": csv_val, "id": competition.id},
        )


def ensure_mxsm_2027_series() -> Series:
    """Public-facing series card for 2027 (under construction until PUBLIC_PLAY)."""
    s = Series.query.filter_by(name="MXSM", year=2027).first()
    start = date(2027, 5, 1)
    end = date(2027, 9, 30)
    if not s:
        s = Series(
            name="MXSM",
            year=2027,
            start_date=start,
            end_date=end,
            is_active=True,
            points_system="mxsm_tippa",
        )
        db.session.add(s)
        db.session.flush()
    else:
        s.is_active = True
        s.start_date = start
        s.end_date = end
    return s


def ensure_mxsm_2026_series() -> Series:
    """2026 sandbox series — roster + real calendar for local tippa tests."""
    s = Series.query.filter_by(name="MXSM", year=2026).first()
    start = _MXSM_2026_CALENDAR[0][1]
    end = _MXSM_2026_CALENDAR[-1][1]
    if not s:
        s = Series(
            name="MXSM",
            year=2026,
            start_date=start,
            end_date=end,
            is_active=False,
            points_system="mxsm_tippa",
        )
        db.session.add(s)
        db.session.flush()
    else:
        s.start_date = start
        s.end_date = end
        s.points_system = "mxsm_tippa"
    return s


def _upsert_mxsm_calendar(
    *, series: Series, calendar: list[tuple[str, date, tuple[str, ...]]]
) -> dict[str, Any]:
    ensure_mxsm_tippa_classes_column()
    created = updated = 0
    ids: list[int] = []
    class_map: dict[str, str] = {}
    for name, event_date, classes in calendar:
        comp = Competition.query.filter_by(name=name, series_id=series.id).first()
        if comp is None:
            comp = Competition.query.filter_by(name=name, series=SERIES_CODE).first()
        if comp is None:
            comp = Competition(
                name=name,
                event_date=event_date,
                series=SERIES_CODE,
                series_id=series.id,
            )
            db.session.add(comp)
            created += 1
        else:
            updated += 1
        comp.series = SERIES_CODE
        comp.series_id = series.id
        comp.event_date = event_date
        if hasattr(comp, "timezone"):
            comp.timezone = "Europe/Stockholm"
        db.session.flush()
        set_competition_tippa_classes(comp, classes)
        ids.append(int(comp.id))
        class_map[name] = tippa_classes_csv(classes)
    return {
        "created": created,
        "updated": updated,
        "competition_ids": ids,
        "classes": class_map,
    }


def ensure_mxsm_2026_calendar(*, series: Series | None = None) -> dict[str, Any]:
    series = series or ensure_mxsm_2026_series()
    return _upsert_mxsm_calendar(series=series, calendar=_MXSM_2026_CALENDAR)


def ensure_mxsm_admin_test_race(*, series: Series | None = None) -> Competition:
    """Future-dated sandbox race under 2026 series (avoids 2027 preseason lock)."""
    ensure_mxsm_tippa_classes_column()
    series = series or ensure_mxsm_2026_series()
    test_date = date.today() + timedelta(days=14)
    comp = Competition.query.filter_by(
        name=ADMIN_TEST_RACE_NAME, series=SERIES_CODE
    ).first()
    if comp is None:
        comp = Competition(
            name=ADMIN_TEST_RACE_NAME,
            event_date=test_date,
            series=SERIES_CODE,
            series_id=series.id,
        )
        db.session.add(comp)
    else:
        comp.series = SERIES_CODE
        comp.series_id = series.id
        if not comp.event_date or comp.event_date < date.today():
            comp.event_date = test_date
    if hasattr(comp, "timezone") and not (comp.timezone or "").strip():
        comp.timezone = "Europe/Stockholm"
    db.session.flush()
    set_competition_tippa_classes(comp, CLASSES_ALL)
    return comp


def _load_roster_rows() -> list[dict[str, Any]]:
    if not _ROSTER_CSV.is_file():
        print(f"[MXSM] Missing roster CSV: {_ROSTER_CSV}")
        return []
    rows: list[dict[str, Any]] = []
    with _ROSTER_CSV.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            cls = (r.get("class") or "").strip()
            name = (r.get("name") or "").strip()
            if not cls or not name:
                continue
            num_raw = (r.get("number") or "").strip()
            try:
                number = int(num_raw) if num_raw else None
            except ValueError:
                number = None
            brand = (r.get("brand") or "").strip() or None
            team = (r.get("team") or "").strip() or None
            rows.append(
                {
                    "class_name": cls,
                    "name": name,
                    "number": number,
                    "brand": brand,
                    "team": team,
                }
            )
    return rows


def ensure_mxsm_2026_roster() -> dict[str, Any]:
    """Upsert tippa-only MXSM riders from data/mxsm_2026_roster.csv."""
    roster = _load_roster_rows()
    created = updated = 0
    by_class: dict[str, int] = {}
    for row in roster:
        class_name = row["class_name"]
        name = row["name"]
        by_class[class_name] = by_class.get(class_name, 0) + 1
        rider = (
            Rider.query.filter_by(name=name, class_name=class_name)
            .filter(Rider.series_participation == "mxsm")
            .first()
        )
        if rider is None:
            rider = Rider.query.filter_by(name=name, class_name=class_name).first()
            sp = (getattr(rider, "series_participation", None) or "").lower() if rider else ""
            if rider and sp not in ("", "mxsm"):
                rider = None
        if rider is None:
            rider = Rider(
                name=name,
                class_name=class_name,
                rider_number=row["number"],
                bike_brand=row["brand"],
                team=row["team"],
                price=1,
                series_participation="mxsm",
            )
            db.session.add(rider)
            created += 1
        else:
            updated += 1
            rider.class_name = class_name
            if row["number"] is not None:
                rider.rider_number = row["number"]
            if row["brand"]:
                rider.bike_brand = row["brand"]
            if row["team"]:
                rider.team = row["team"]
            rider.series_participation = "mxsm"
            if rider.price is None:
                rider.price = 1
    db.session.flush()
    return {
        "created": created,
        "updated": updated,
        "roster_size": len(roster),
        "by_class": by_class,
    }


def mxsm_roster_query(*, classes: tuple[str, ...] | None = None):
    cls = classes or CLASSES_ALL
    return Rider.query.filter(
        Rider.class_name.in_(cls),
        Rider.series_participation == "mxsm",
    )


def mxsm_official_roster_ids(*, classes: tuple[str, ...] | None = None) -> set[int]:
    return {int(r.id) for r in mxsm_roster_query(classes=classes).all()}


def mxsm_roster_for_competition(competition: Competition | None):
    return mxsm_roster_query(classes=get_mxsm_tippa_classes(competition))


def mxsm_class_label(class_name: str | None) -> str:
    """Swedish UI labels for MXSM tippa classes."""
    c = (class_name or "").strip().lower()
    if c == CLASS_MX1:
        return "MX1"
    if c == CLASS_MX2:
        return "MX2"
    if c == CLASS_U17:
        return "U17"
    return (class_name or "").upper() or "?"


def mxsm_tippa_hs_classes(competition: Competition | None) -> tuple[str, ...]:
    """Holeshot classes required for this race (same set as tippa_classes)."""
    return get_mxsm_tippa_classes(competition)


def ensure_mxsm_scaffold() -> dict[str, Any]:
    """Idempotent bootstrap: 2027 UC series, 2026 calendar+roster, admin test race."""
    try:
        from services.schema_patches import (
            _ensure_racerx_bio_skip_column,
            _ensure_rider_bio_sv_columns,
        )

        _ensure_rider_bio_sv_columns()
        _ensure_racerx_bio_skip_column()
    except Exception as e:
        print(f"[MXSM-SEED] rider column patch skipped: {e}")
    ensure_mxsm_tippa_classes_column()
    s2027 = ensure_mxsm_2027_series()
    s2026 = ensure_mxsm_2026_series()
    cal_2026 = ensure_mxsm_2026_calendar(series=s2026)
    roster = ensure_mxsm_2026_roster()
    test_race = ensure_mxsm_admin_test_race(series=s2026)
    db.session.commit()
    info = {
        "series_2027_id": int(s2027.id),
        "series_2026_id": int(s2026.id),
        "admin_test_competition_id": int(test_race.id),
        "admin_test_date": test_race.event_date.isoformat() if test_race.event_date else None,
        "admin_test_classes": tippa_classes_csv(get_mxsm_tippa_classes(test_race)),
        "public_play": mxsm_public_play_enabled(),
        "calendar_2026": cal_2026,
        "roster": roster,
    }
    print(
        f"[MXSM-SEED] OK 2027={s2027.id} 2026={s2026.id} "
        f"test={test_race.id} races={len(cal_2026['competition_ids'])} "
        f"roster+={roster['created']}/{roster['roster_size']}"
    )
    return info
