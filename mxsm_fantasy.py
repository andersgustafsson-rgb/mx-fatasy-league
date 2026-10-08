"""MXSM (Motocross SM) scaffold — under construction for 2027.

Public: homepage card shows Under construction.
No tippa / scoring / roster yet — flip MXSM_PUBLIC_PLAY when ready.
"""
from __future__ import annotations

from datetime import date

from models import Series, db

# Flip when ready for public tippa (2027 season).
MXSM_PUBLIC_PLAY = False

SERIES_CODE = "MXSM"


def is_mxsm_series(series: str | None) -> bool:
    return (series or "").strip().upper() == SERIES_CODE


def mxsm_public_play_enabled() -> bool:
    return bool(MXSM_PUBLIC_PLAY)


def mxsm_user_can_play(*, is_admin: bool) -> bool:
    """Public tippa locked until MXSM_PUBLIC_PLAY; admins always can test."""
    return bool(is_admin) or mxsm_public_play_enabled()


def ensure_mxsm_2027_series() -> Series:
    """Public-facing series card for 2027 (under construction until PUBLIC_PLAY)."""
    s = Series.query.filter_by(name="MXSM", year=2027).first()
    # Placeholder window — real MXSM calendar comes later.
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


def ensure_mxsm_scaffold() -> dict:
    """Idempotent boot hook — series row only for now."""
    s = ensure_mxsm_2027_series()
    db.session.commit()
    return {
        "series_id": int(s.id),
        "year": int(s.year or 2027),
        "public_play": mxsm_public_play_enabled(),
    }
