"""Special visual themes for race picks (Military Appreciation, etc.)."""
from __future__ import annotations

from typing import Any

# Official MAD weekends by (year, series, competition name).
MILITARY_APPRECIATION_RACES = frozenset(
    {
        (2026, "SX", "Arlington"),
        (2027, "SX", "Seattle"),
    }
)

_MONTHS_EN = (
    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
)
_MONTHS_EN_SHORT = (
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
)
_COAST_LABEL = {
    "west": "250SX West",
    "east": "250SX East",
    "showdown": "East/West Showdown",
    "both": "250SX both coasts",
}


def _competition_year(competition: Any) -> int | None:
    ed = getattr(competition, "event_date", None)
    if ed is not None and getattr(ed, "year", None):
        return int(ed.year)
    series = getattr(competition, "series_ref", None)
    year = getattr(series, "year", None) if series is not None else None
    return int(year) if year else None


def _sx_calendar_race(competition: Any) -> dict[str, Any] | None:
    series = (getattr(competition, "series", None) or "").strip().upper()
    year = _competition_year(competition)
    name = (getattr(competition, "name", None) or "").strip()
    if series != "SX" or not year or int(year) < 2027:
        return None
    try:
        from ama_2027_calendar import get_sx_2027_race_info

        return get_sx_2027_race_info(name)
    except Exception:
        return None


def is_military_appreciation_race(competition: Any) -> bool:
    """True for AMA SX Military Appreciation Day weekends."""
    if competition is None:
        return False
    name = (getattr(competition, "name", None) or "").strip()
    if "military appreciation" in name.lower():
        return True

    series = (getattr(competition, "series", None) or "").strip().upper()
    year = _competition_year(competition)
    if year and series and (year, series, name) in MILITARY_APPRECIATION_RACES:
        return True

    race = _sx_calendar_race(competition)
    return bool(race and race.get("is_military_appreciation"))


def military_theme_meta(competition: Any) -> dict[str, Any]:
    """Copy + round/coast labels for the Military Appreciation Day hero."""
    name = (getattr(competition, "name", None) or "").strip()
    year = _competition_year(competition)
    coast = (getattr(competition, "coast_250", None) or "").strip().lower()
    round_n = None
    venue = ""
    race = _sx_calendar_race(competition)
    if race:
        round_n = race.get("round")
        venue = race.get("venue") or ""
        coast = (race.get("coast_250") or coast or "").strip().lower()

    ed = getattr(competition, "event_date", None)
    date_short = ""
    date_long = ""
    if ed is not None and getattr(ed, "month", None):
        month_i = int(ed.month) - 1
        date_short = f"{int(ed.day)} {_MONTHS_EN_SHORT[month_i]} {int(ed.year)}"
        date_long = f"{int(ed.day)} {_MONTHS_EN[month_i]} {int(ed.year)}"

    return {
        "city": name.upper(),
        "year": year,
        "round": round_n,
        "coast": coast,
        "coast_label": _COAST_LABEL.get(coast, ""),
        "venue": venue,
        "date_short": date_short,
        "date_long": date_long,
        "motto": "HONOR · COURAGE",
    }


def race_card_marks(competition: Any) -> dict[str, bool]:
    """Icons for series schedule cards: Triple Crown, East/West, Military Appreciation."""
    series = (getattr(competition, "series", None) or "").strip().upper()
    if series != "SX":
        return {"triple_crown": False, "showdown": False, "military": False}
    race = _sx_calendar_race(competition)
    coast = (
        (race.get("coast_250") if race else None)
        or getattr(competition, "coast_250", None)
        or ""
    )
    coast = str(coast).strip().lower()
    triple = bool(race.get("is_triple_crown")) if race else False
    if not triple:
        triple = bool(getattr(competition, "is_triple_crown", False))
    return {
        "triple_crown": triple,
        "showdown": coast in ("showdown", "both"),
        "military": is_military_appreciation_race(competition),
    }
